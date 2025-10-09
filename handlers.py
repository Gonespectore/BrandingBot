import logging
from telegram import Update, InputMediaPhoto
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import TelegramError

from db import get_db, UserPreferences
from keyboards import (
    get_main_menu, get_prefix_menu, get_suffix_menu,
    get_keyword_menu, get_publish_menu, get_cancel_keyboard,
    get_confirm_reset_keyboard
)

logger = logging.getLogger(__name__)

# États pour les conversations
WAITING_PREFIX = 1
WAITING_SUFFIX = 2
WAITING_KEYWORD_FIND = 3
WAITING_KEYWORD_REPLACE = 4
WAITING_TARGET_CHAT = 5


# --- Images pour le menu principal (URLs d'exemple) ---
WELCOME_IMAGES = [
    "https://images.unsplash.com/photo-1611162617474-5b21e879e113?w=400",
    "https://images.unsplash.com/photo-1614680376593-902f74cf0d41?w=400",
    "https://images.unsplash.com/photo-1614680376408-81e91ffe3db7?w=400"
]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /start avec image et menu interactif"""
    user = update.effective_user
    
    # Créer ou récupérer les préférences
    db = next(get_db())
    prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user.id).first()
    if not prefs:
        prefs = UserPreferences(user_id=user.id)
        db.add(prefs)
        db.commit()
    db.close()
    
    welcome_text = (
        f"👋 <b>Bienvenue {user.first_name}!</b>\n\n"
        "🤖 <b>Bot de Messagerie Avancé</b>\n\n"
        "✨ <b>Fonctionnalités:</b>\n"
        "• Ajout de préfixe/suffixe\n"
        "• Remplacement de mots-clés\n"
        "• Publication automatique vers canal\n"
        "• Traitement massif (100+ messages)\n\n"
        "📋 Sélectionnez une option ci-dessous:"
    )
    
    try:
        # Envoyer une image aléatoire avec le menu
        import random
        photo_url = random.choice(WELCOME_IMAGES)
        
        await update.message.reply_photo(
            photo=photo_url,
            caption=welcome_text,
            reply_markup=get_main_menu(),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Erreur envoi image: {e}")
        await update.message.reply_text(
            welcome_text,
            reply_markup=get_main_menu(),
            parse_mode="HTML"
        )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestionnaire pour tous les boutons inline"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    db = next(get_db())
    prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
    if not prefs:
        prefs = UserPreferences(user_id=user_id)
        db.add(prefs)
        db.commit()
        db.refresh(prefs)
    
    # Navigation dans les menus
    if data == "menu_main":
        text = "📋 <b>Menu Principal</b>\n\nSélectionnez une option:"
        await query.edit_message_caption(
            caption=text,
            reply_markup=get_main_menu(),
            parse_mode="HTML"
        )
    
    elif data == "menu_prefix":
        text = "📝 <b>Gestion du Préfixe</b>\n\n"
        if prefs.prefix:
            text += f"Préfixe actuel: <code>{prefs.prefix}</code>"
        else:
            text += "Aucun préfixe défini"
        await query.edit_message_caption(
            caption=text,
            reply_markup=get_prefix_menu(),
            parse_mode="HTML"
        )
    
    elif data == "menu_suffix":
        text = "📌 <b>Gestion du Suffixe</b>\n\n"
        if prefs.suffix:
            text += f"Suffixe actuel: <code>{prefs.suffix}</code>"
        else:
            text += "Aucun suffixe défini"
        await query.edit_message_caption(
            caption=text,
            reply_markup=get_suffix_menu(),
            parse_mode="HTML"
        )
    
    elif data == "menu_keyword":
        text = "🔄 <b>Remplacement de Mots-clés</b>\n\n"
        if prefs.keyword_find:
            text += f"Chercher: <code>{prefs.keyword_find}</code>\n"
            text += f"Remplacer par: <code>{prefs.keyword_replace}</code>"
        else:
            text += "Aucun remplacement défini"
        await query.edit_message_caption(
            caption=text,
            reply_markup=get_keyword_menu(),
            parse_mode="HTML"
        )
    
    elif data == "menu_publish":
        text = "📢 <b>Mode Publication</b>\n\n"
        if prefs.publish_mode:
            text += f"✅ Activé\nCanal cible: <code>{prefs.target_chat_id}</code>"
        else:
            text += "❌ Désactivé"
        await query.edit_message_caption(
            caption=text,
            reply_markup=get_publish_menu(prefs.publish_mode),
            parse_mode="HTML"
        )
    
    elif data == "menu_status":
        text = "ℹ️ <b>État de vos paramètres</b>\n\n"
        text += f"📝 Préfixe: <code>{prefs.prefix or '(vide)'}</code>\n"
        text += f"📌 Suffixe: <code>{prefs.suffix or '(vide)'}</code>\n"
        text += f"🔍 Mot à remplacer: <code>{prefs.keyword_find or '(vide)'}</code>\n"
        text += f"✨ Remplacer par: <code>{prefs.keyword_replace or '(vide)'}</code>\n"
        text += f"📢 Mode publication: {'✅ Activé' if prefs.publish_mode else '❌ Désactivé'}\n"
        if prefs.target_chat_id:
            text += f"📍 Canal cible: <code>{prefs.target_chat_id}</code>"
        await query.edit_message_caption(
            caption=text,
            reply_markup=get_main_menu(),
            parse_mode="HTML"
        )
    
    elif data == "menu_reset":
        text = "⚠️ <b>Réinitialisation</b>\n\nÊtes-vous sûr de vouloir réinitialiser tous vos paramètres?"
        await query.edit_message_caption(
            caption=text,
            reply_markup=get_confirm_reset_keyboard(),
            parse_mode="HTML"
        )
    
    elif data == "confirm_reset":
        prefs.prefix = ""
        prefs.suffix = ""
        prefs.keyword_find = ""
        prefs.keyword_replace = ""
        prefs.publish_mode = False
        prefs.target_chat_id = None
        db.commit()
        
        text = "✅ <b>Réinitialisation réussie!</b>\n\nTous vos paramètres ont été supprimés."
        await query.edit_message_caption(
            caption=text,
            reply_markup=get_main_menu(),
            parse_mode="HTML"
        )
    
    # Actions de définition
    elif data == "set_prefix":
        context.user_data['awaiting'] = WAITING_PREFIX
        await query.edit_message_caption(
            caption="✏️ <b>Définir le préfixe</b>\n\nEnvoyez le texte à utiliser comme préfixe:",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML"
        )
    
    elif data == "set_suffix":
        context.user_data['awaiting'] = WAITING_SUFFIX
        await query.edit_message_caption(
            caption="✏️ <b>Définir le suffixe</b>\n\nEnvoyez le texte à utiliser comme suffixe:",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML"
        )
    
    elif data == "set_keyword_find":
        context.user_data['awaiting'] = WAITING_KEYWORD_FIND
        await query.edit_message_caption(
            caption="🔍 <b>Mot à remplacer</b>\n\nEnvoyez le mot ou phrase à détecter:",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML"
        )
    
    elif data == "set_keyword_replace":
        context.user_data['awaiting'] = WAITING_KEYWORD_REPLACE
        await query.edit_message_caption(
            caption="✨ <b>Texte de remplacement</b>\n\nEnvoyez le texte qui remplacera le mot-clé:",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML"
        )
    
    elif data == "set_target_chat":
        context.user_data['awaiting'] = WAITING_TARGET_CHAT
        await query.edit_message_caption(
            caption="📍 <b>Canal cible</b>\n\nEnvoyez l'ID du canal/groupe (ex: -1001234567890)\n\n"
                   "💡 Pour obtenir l'ID: ajoutez @userinfobot à votre canal",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML"
        )
    
    # Actions de suppression
    elif data == "clear_prefix":
        prefs.prefix = ""
        db.commit()
        await query.edit_message_caption(
            caption="✅ <b>Préfixe supprimé</b>",
            reply_markup=get_prefix_menu(),
            parse_mode="HTML"
        )
    
    elif data == "clear_suffix":
        prefs.suffix = ""
        db.commit()
        await query.edit_message_caption(
            caption="✅ <b>Suffixe supprimé</b>",
            reply_markup=get_suffix_menu(),
            parse_mode="HTML"
        )
    
    elif data == "clear_keyword":
        prefs.keyword_find = ""
        prefs.keyword_replace = ""
        db.commit()
        await query.edit_message_caption(
            caption="✅ <b>Remplacement supprimé</b>",
            reply_markup=get_keyword_menu(),
            parse_mode="HTML"
        )
    
    elif data == "toggle_publish":
        prefs.publish_mode = not prefs.publish_mode
        db.commit()
        status = "activé ✅" if prefs.publish_mode else "désactivé ❌"
        text = f"📢 <b>Mode publication {status}</b>"
        await query.edit_message_caption(
            caption=text,
            reply_markup=get_publish_menu(prefs.publish_mode),
            parse_mode="HTML"
        )
    
    db.close()


async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestion des entrées textuelles selon le contexte"""
    user_id = update.effective_user.id
    text = update.message.text
    
    # Vérifier si on attend une entrée spécifique
    awaiting = context.user_data.get('awaiting')
    
    if awaiting:
        db = next(get_db())
        prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
        
        if awaiting == WAITING_PREFIX:
            prefs.prefix = text
            db.commit()
            await update.message.reply_text(
                f"✅ <b>Préfixe défini:</b> <code>{text}</code>",
                parse_mode="HTML"
            )
        
        elif awaiting == WAITING_SUFFIX:
            prefs.suffix = text
            db.commit()
            await update.message.reply_text(
                f"✅ <b>Suffixe défini:</b> <code>{text}</code>",
                parse_mode="HTML"
            )
        
        elif awaiting == WAITING_KEYWORD_FIND:
            prefs.keyword_find = text
            db.commit()
            await update.message.reply_text(
                f"✅ <b>Mot-clé défini:</b> <code>{text}</code>",
                parse_mode="HTML"
            )
        
        elif awaiting == WAITING_KEYWORD_REPLACE:
            prefs.keyword_replace = text
            db.commit()
            await update.message.reply_text(
                f"✅ <b>Remplacement défini:</b> <code>{text}</code>",
                parse_mode="HTML"
            )
        
        elif awaiting == WAITING_TARGET_CHAT:
            try:
                chat_id = int(text)
                prefs.target_chat_id = chat_id
                db.commit()
                await update.message.reply_text(
                    f"✅ <b>Canal cible défini:</b> <code>{chat_id}</code>",
                    parse_mode="HTML"
                )
            except ValueError:
                await update.message.reply_text(
                    "❌ <b>Erreur:</b> ID invalide. Envoyez un nombre (ex: -1001234567890)",
                    parse_mode="HTML"
                )
                db.close()
                return
        
        context.user_data['awaiting'] = None
        db.close()
    else:
        # Traitement normal du message
        await process_message(update, context)


async def process_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Traite les messages avec les transformations définies"""
    user_id = update.effective_user.id
    text = update.message.text
    
    db = next(get_db())
    prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
    
    if not prefs:
        prefs = UserPreferences(user_id=user_id)
        db.add(prefs)
        db.commit()
        db.refresh(prefs)
    
    # Appliquer les transformations
    processed_text = text
    
    # Remplacement de mots-clés
    if prefs.keyword_find and prefs.keyword_replace:
        processed_text = processed_text.replace(prefs.keyword_find, prefs.keyword_replace)
    
    # Ajout préfixe/suffixe
    processed_text = f"{prefs.prefix}{processed_text}{prefs.suffix}"
    
    # Mode publication
    if prefs.publish_mode and prefs.target_chat_id:
        try:
            await context.bot.send_message(
                chat_id=prefs.target_chat_id,
                text=processed_text
            )
            await update.message.reply_text("✅ Message publié dans le canal!")
        except TelegramError as e:
            logger.error(f"Erreur publication: {e}")
            await update.message.reply_text(
                f"❌ Erreur lors de la publication:\n{str(e)}\n\n"
                "Vérifiez que le bot est administrateur du canal."
            )
    else:
        # Réponse dans le même chat
        await update.message.reply_text(processed_text)
    
    db.close()