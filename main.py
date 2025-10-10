import os
import logging
from fastapi import FastAPI, Request, HTTPException
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ContextTypes, filters
)
from contextlib import asynccontextmanager

from db import get_db, UserPreferences
from handlers import (
    start, button_callback, handle_all_messages,
    stats_command, reset_command
)
# --- Logging optimisé ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

import telegram
logger.info(f"Version: {telegram.__version__}")

# --- Configuration ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

if not TELEGRAM_TOKEN:
    raise RuntimeError("❌ Variable manquante : TELEGRAM_BOT_TOKEN")
if not WEBHOOK_URL:
    raise RuntimeError("❌ Variable manquante : WEBHOOK_URL")

# --- Logging optimisé ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Réduire le verbosity de certains loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

# --- Application Telegram ---
application = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestion du cycle de vie - MODE WEBHOOK"""
    global application
    
    logger.info("🚀 Démarrage du bot en mode WEBHOOK...")
    
    try:
        # Créer l'application
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        
        # Enregistrer les handlers
        # Capture TOUS les messages (texte, médias, etc.) sauf les commandes
        all_media_filters = (
            filters.TEXT |
            filters.PHOTO |
            filters.VIDEO |
            filters.DOCUMENT |  # ← TOUT EN MAJUSCULES
            filters.AUDIO |
            filters.VOICE |
            filters.CONTACT |
            filters.LOCATION |
            filters.STICKER |
            filters.ANIMATION
        )
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", start))
        application.add_handler(CommandHandler("stats", stats_command))
        application.add_handler(CommandHandler("reset", reset_command))
        application.add_handler(CallbackQueryHandler(button_callback))
        
        # Handler universel pour TOUS les messages non-commandes
        application.add_handler(MessageHandler(
            all_media_filters & ~filters.COMMAND,
            handle_all_messages
        ))
        
        # CRITIQUE: Pour webhook, seulement initialize() - PAS start()
        await application.initialize()
        logger.info("✅ Application initialisée")
        
        # Configurer le webhook
        webhook_info = await application.bot.get_webhook_info()
        
        if webhook_info.url != WEBHOOK_URL:
            await application.bot.set_webhook(
                url=WEBHOOK_URL,
                allowed_updates=["message", "callback_query"],
                drop_pending_updates=True
            )
            logger.info(f"✅ Webhook configuré: {WEBHOOK_URL}")
        else:
            logger.info(f"✅ Webhook déjà actif: {WEBHOOK_URL}")
        
        # Vérifier la connexion
        bot_info = await application.bot.get_me()
        logger.info(f"✅ Bot connecté: @{bot_info.username} (ID: {bot_info.id})")
        
    except Exception as e:
        logger.error(f"❌ Erreur initialisation: {e}", exc_info=True)
        raise
    
    yield
    
    # Shutdown
    logger.info("🛑 Arrêt du bot...")
    try:
        await application.bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Webhook supprimé")
    except:
        pass
    
    await application.shutdown()
    logger.info("✅ Bot arrêté proprement")


# --- FastAPI App ---
app = FastAPI(
    title="Telegram Advanced Bot",
    version="2.0.0",
    lifespan=lifespan
)


# --- Webhook Endpoint ---
@app.post("/webhook")
async def telegram_webhook(request: Request):
    """
    Endpoint principal pour recevoir les updates Telegram
    CRITIQUE: Utiliser process_update() et non update_queue en mode webhook!
    """
    try:
        # Récupérer les données
        data = await request.json()
        
        # Logger pour debug (optionnel)
        if data.get("message"):
            user_id = data["message"].get("from", {}).get("id")
            text = data["message"].get("text", "")
            logger.info(f"📨 Message reçu de {user_id}: {text[:50]}")
        elif data.get("callback_query"):
            user_id = data["callback_query"].get("from", {}).get("id")
            callback_data = data["callback_query"].get("data", "")
            logger.info(f"🔘 Callback de {user_id}: {callback_data}")
        
        # Convertir en Update Telegram
        update = Update.de_json(data, application.bot)
        
        # CRITIQUE: En webhook, utiliser process_update() directement
        await application.process_update(update)
        
        return {"ok": True}
    
    except Exception as e:
        logger.error(f"❌ Erreur webhook: {e}", exc_info=True)
        # Ne pas raise pour éviter que Telegram considère le webhook comme cassé
        return {"ok": False, "error": str(e)}


# --- Health Check ---
@app.get("/")
async def health_check():
    """Endpoint de santé"""
    try:
        bot_info = await application.bot.get_me()
        webhook_info = await application.bot.get_webhook_info()
        
        return {
            "status": "✅ Online",
            "bot": {
                "username": f"@{bot_info.username}",
                "id": bot_info.id,
                "name": bot_info.first_name
            },
            "webhook": {
                "url": webhook_info.url,
                "pending_updates": webhook_info.pending_update_count
            },
            "features": [
                "Prefix/Suffix automatique",
                "Keyword Replacement intelligent",
                "Publish Mode vers canal",
                "Bulk Processing (100+ messages)",
                "Interactive Menu avec images",
                "Statistiques détaillées",
                "Tutoriel intégré",
                "Retry exponentiel"
            ],
            "version": "2.0.0"
        }
    except Exception as e:
        logger.error(f"Erreur health check: {e}")
        return {
            "status": "⚠️ Partial",
            "error": str(e)
        }


@app.get("/stats")
async def global_stats():
    """Statistiques globales du bot"""
    from sqlalchemy import func
    
    try:
        with get_db() as db:
            total_users = db.query(UserPreferences).count()
            active_publish = db.query(UserPreferences).filter(
                UserPreferences.publish_mode == True
            ).count()
            active_buffer = db.query(UserPreferences).filter(
                UserPreferences.buffer_mode == True
            ).count()
            
            total_processed = db.query(UserPreferences).with_entities(
                func.sum(UserPreferences.messages_processed)
            ).scalar() or 0
            
            total_failed = db.query(UserPreferences).with_entities(
                func.sum(UserPreferences.messages_failed)
            ).scalar() or 0
        
        success_rate = 0
        if total_processed + total_failed > 0:
            success_rate = (total_processed / (total_processed + total_failed)) * 100
        
        return {
            "users": {
                "total": total_users,
                "with_publish_mode": active_publish,
                "with_buffer_mode": active_buffer
            },
            "messages": {
                "total_processed": total_processed,
                "total_failed": total_failed,
                "success_rate": f"{success_rate:.2f}%"
            },
            "processor": {
                "max_concurrent": 15,
                "base_delay": 0.05,
                "retry_count": 3
            }
        }
    except Exception as e:
        logger.error(f"Erreur stats: {e}")
        return {"error": str(e)}


@app.get("/webhook/info")
async def webhook_info():
    """Informations sur le webhook"""
    try:
        info = await application.bot.get_webhook_info()
        return {
            "url": info.url,
            "has_custom_certificate": info.has_custom_certificate,
            "pending_update_count": info.pending_update_count,
            "last_error_date": info.last_error_date,
            "last_error_message": info.last_error_message,
            "max_connections": info.max_connections,
            "allowed_updates": info.allowed_updates
        }
    except Exception as e:
        return {"error": str(e)}


@app.post("/webhook/reset")
async def reset_webhook():
    """Force la reconfiguration du webhook (debug)"""
    try:
        await application.bot.delete_webhook(drop_pending_updates=True)
        await application.bot.set_webhook(
            url=WEBHOOK_URL,
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=True
        )
        return {"status": "✅ Webhook reconfiguré", "url": WEBHOOK_URL}
    except Exception as e:
        logger.error(f"Erreur reset webhook: {e}")
        return {"status": "❌ Erreur", "error": str(e)}


# --- Gestion d'erreurs ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handler global pour les erreurs non gérées"""
    logger.error(f"❌ Erreur non gérée: {exc}", exc_info=True)
    return {
        "status": "error",
        "message": str(exc),
        "path": str(request.url)
    }


# --- Point d'entrée ---
if __name__ == "__main__":
    import uvicorn
    
    raw_port = os.getenv("PORT")
    if raw_port is None or raw_port == "":
        raise RuntimeError("❌ La variable d'environnement PORT est manquante ou vide. Railway doit la fournir.")
    
    try:
        port = int(raw_port)
    except ValueError:
        raise RuntimeError(f"❌ PORT invalide: '{raw_port}'. Doit être un nombre entier.")
    
    logger.info(f"🚀 Démarrage sur le port {port}")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
        access_log=True
    )