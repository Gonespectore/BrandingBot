import os
import logging
from fastapi import FastAPI, Request, HTTPException
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, filters, ContextTypes
)
from contextlib import asynccontextmanager

from db import get_db, UserPreferences
from handlers import start, button_callback, handle_text_input
from message_processor import message_processor, handle_bulk_processing

# --- Vérification des variables d'environnement ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

if not TELEGRAM_TOKEN:
    raise RuntimeError("❌ Variable manquante : TELEGRAM_BOT_TOKEN")
if not WEBHOOK_URL:
    raise RuntimeError("❌ Variable manquante : WEBHOOK_URL")

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Variables globales ---
application = None
user_message_buffer = {}  # Pour le traitement en lot

# --- Lifecycle management ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestion du cycle de vie de l'application"""
    global application
    
    # Startup
    logger.info("🚀 Démarrage de l'application...")
    
    # Initialiser le bot
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Enregistrer les handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(CommandHandler("process", process_bulk_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))
    
    # Initialiser le bot (sans démarrer le polling)
    await application.initialize()
    await application.start()
    
    # Configurer le webhook
    try:
        webhook_info = await application.bot.get_webhook_info()
        if webhook_info.url != WEBHOOK_URL:
            await application.bot.set_webhook(url=WEBHOOK_URL)
            logger.info(f"✅ Webhook configuré: {WEBHOOK_URL}")
        else:
            logger.info(f"✅ Webhook déjà configuré: {WEBHOOK_URL}")
    except Exception as e:
        logger.error(f"❌ Erreur configuration webhook: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("🛑 Arrêt de l'application...")
    await application.stop()
    await application.shutdown()

# --- FastAPI App ---
app = FastAPI(lifespan=lifespan)


# --- Commandes supplémentaires ---
async def process_bulk_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Commande /process pour traiter plusieurs messages en lot
    Usage: /process puis envoyer plusieurs messages qui seront bufferisés
    """
    user_id = update.effective_user.id
    
    if user_id not in user_message_buffer:
        user_message_buffer[user_id] = []
    
    if not context.args:
        # Initialiser le mode buffer
        user_message_buffer[user_id] = []
        await update.message.reply_text(
            "📥 <b>Mode traitement en lot activé</b>\n\n"
            "Envoyez vos messages (jusqu'à 100)\n"
            "Utilisez /process done pour traiter\n"
            "Utilisez /process cancel pour annuler",
            parse_mode="HTML"
        )
        return
    
    command = context.args[0].lower()
    
    if command == "done":
        messages = user_message_buffer.get(user_id, [])
        if not messages:
            await update.message.reply_text("❌ Aucun message à traiter")
            return
        
        status_msg = await update.message.reply_text(
            f"⚙️ <b>Traitement de {len(messages)} messages...</b>",
            parse_mode="HTML"
        )
        
        result = await handle_bulk_processing(
            user_id=user_id,
            messages=messages,
            context=context,
            status_message=status_msg
        )
        
        await status_msg.edit_text(
            f"✅ <b>Traitement terminé!</b>\n\n"
            f"📊 Total: {result['total']}\n"
            f"✅ Réussis: {result['successful']}\n"
            f"❌ Échecs: {result['failed']}",
            parse_mode="HTML"
        )
        
        user_message_buffer[user_id] = []
    
    elif command == "cancel":
        user_message_buffer[user_id] = []
        await update.message.reply_text("❌ Traitement en lot annulé")
    
    elif command == "status":
        count = len(user_message_buffer.get(user_id, []))
        await update.message.reply_text(
            f"📊 Messages en attente: {count}/100"
        )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Affiche les statistiques du bot"""
    user_id = update.effective_user.id
    
    db = next(get_db())
    prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
    
    if not prefs:
        await update.message.reply_text("❌ Aucune donnée disponible")
        db.close()
        return
    
    stats_text = (
        "📊 <b>Vos Statistiques</b>\n\n"
        f"👤 User ID: <code>{user_id}</code>\n"
        f"📝 Préfixe: {'✅' if prefs.prefix else '❌'}\n"
        f"📌 Suffixe: {'✅' if prefs.suffix else '❌'}\n"
        f"🔄 Remplacement: {'✅' if prefs.keyword_find else '❌'}\n"
        f"📢 Mode publication: {'✅ Activé' if prefs.publish_mode else '❌ Désactivé'}\n"
        f"📅 Dernière mise à jour: {prefs.updated_at.strftime('%Y-%m-%d %H:%M')}\n\n"
        f"⚡ Capacité: Jusqu'à 100+ messages simultanés"
    )
    
    await update.message.reply_text(stats_text, parse_mode="HTML")
    db.close()


# --- Endpoint Webhook ---
@app.post("/webhook")
async def telegram_webhook(request: Request):
    """Reçoit les updates de Telegram"""
    try:
        json_data = await request.json()
        update = Update.de_json(json_data, application.bot)
        
        # Gestion du buffer pour le traitement en lot
        if update.message and update.message.text:
            user_id = update.effective_user.id
            if user_id in user_message_buffer and not update.message.text.startswith('/'):
                # Ajouter au buffer
                user_message_buffer[user_id].append(update.message.text)
                
                # Limiter à 100 messages
                if len(user_message_buffer[user_id]) >= 100:
                    await update.message.reply_text(
                        "⚠️ <b>Limite atteinte (100 messages)</b>\n\n"
                        "Utilisez /process done pour traiter",
                        parse_mode="HTML"
                    )
                else:
                    # Confirmer silencieusement l'ajout
                    await update.message.reply_text(
                        f"✅ Message {len(user_message_buffer[user_id])}/100 ajouté"
                    )
                return {"status": "buffered"}
        
        # Traiter normalement
        await application.update_queue.put(update)
        return {"status": "ok"}
    
    except Exception as e:
        logger.error(f"❌ Erreur webhook: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail="Invalid update")


# --- Health Check ---
@app.get("/")
async def health_check():
    """Endpoint de santé"""
    return {
        "status": "✅ Online",
        "bot": "Telegram Advanced Bot",
        "webhook": WEBHOOK_URL,
        "features": [
            "Prefix/Suffix",
            "Keyword Replacement",
            "Publish Mode",
            "Bulk Processing (100+ messages)",
            "Interactive Menu"
        ],
        "version": "2.0.0"
    }


@app.get("/stats")
async def global_stats():
    """Statistiques globales"""
    db = next(get_db())
    total_users = db.query(UserPreferences).count()
    active_publish = db.query(UserPreferences).filter(
        UserPreferences.publish_mode == True
    ).count()
    db.close()
    
    return {
        "total_users": total_users,
        "active_publish_mode": active_publish,
        "processor_stats": {
            "max_concurrent": message_processor.max_concurrent,
            "processed_total": message_processor.processed_count,
            "failed_total": message_processor.failed_count
        }
    }


# --- Gestion des erreurs ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"❌ Erreur non gérée: {exc}", exc_info=True)
    return {
        "status": "error",
        "message": str(exc)
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)