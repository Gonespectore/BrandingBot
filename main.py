# main.py
import os
import logging
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from db import get_db, UserPreferences

# --- Config ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # ex: https://mon-bot.up.railway.app/webhook

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Initialisation du bot ---
app = FastAPI()
application = Application.builder().token(TELEGRAM_TOKEN).build()

# --- Commandes Telegram ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Bonjour ! Envoyez-moi un message, et je vous répondrai avec votre préfixe/suffixe.\n"
        "Utilisez :\n"
        "/setprefix <texte>\n"
        "/setsuffix <texte>\n"
        "/reset"
    )

async def set_prefix(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage : /setprefix <texte>")
        return
    prefix = " ".join(context.args)
    user_id = update.effective_user.id

    db = next(get_db())
    prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
    if not prefs:
        prefs = UserPreferences(user_id=user_id)
        db.add(prefs)
    prefs.prefix = prefix
    db.commit()
    db.close()
    await update.message.reply_text(f"✅ Préfixe défini : `{prefix}`")

async def set_suffix(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage : /setsuffix <texte>")
        return
    suffix = " ".join(context.args)
    user_id = update.effective_user.id

    db = next(get_db())
    prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
    if not prefs:
        prefs = UserPreferences(user_id=user_id)
        db.add(prefs)
    prefs.suffix = suffix
    db.commit()
    db.close()
    await update.message.reply_text(f"✅ Suffixe défini : `{suffix}`")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db = next(get_db())
    prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
    if prefs:
        prefs.prefix = ""
        prefs.suffix = ""
        db.commit()
    db.close()
    await update.message.reply_text("✅ Préférences réinitialisées.")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    db = next(get_db())
    prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
    if not prefs:
        prefs = UserPreferences(user_id=user_id)
        db.add(prefs)
        db.commit()
        db.refresh(prefs)
    db.close()

    response = f"{prefs.prefix}{text}{prefs.suffix}"
    await update.message.reply_text(response)

# --- Enregistrement des handlers ---
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("setprefix", set_prefix))
application.add_handler(CommandHandler("setsuffix", set_suffix))
application.add_handler(CommandHandler("reset", reset))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

# --- Webhook endpoint ---
@app.on_event("startup")
async def set_webhook():
    await application.bot.set_webhook(url=WEBHOOK_URL)
    logger.info(f"Webhook défini sur {WEBHOOK_URL}")

@app.post("/webhook")
async def telegram_webhook(request: Request):
    update = Update.de_json(await request.json(), application.bot)
    await application.update_queue.put(update)
    return {"status": "ok"}

# --- Point de santé (optionnel mais utile pour Railway) ---
@app.get("/")
async def health():
    return {"status": "alive", "bot": "running"}