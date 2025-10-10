import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import TelegramError

from db import (
    get_db, UserPreferences, get_or_create_user, 
    clear_buffer, get_buffer_messages, add_to_buffer,
    update_user_activity
)
from keyboards import *
from message_processor import handle_bulk_processing, validate_chat_id

logger = logging.getLogger(__name__)

# États pour les conversations
WAITING_PREFIX = "waiting_prefix"
WAITING_SUFFIX = "waiting_suffix"
WAITING_KEYWORD_FIND = "waiting_keyword_find"
WAITING_KEYWORD_REPLACE = "waiting_keyword_replace"
WAITING_TARGET_CHAT = "waiting_target_chat"

# Images de bienvenue robustes (base64 ou URLs stables)
WELCOME_IMAGE = "https://images.unsplash.com/photo-1614680376593-902f74cf0d41?w=800&q=80"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /start avec interface complète"""
    user = update.effective_user
    user_id = user.id
    
    # Créer ou récupérer l'utilisateur
    with get_db() as db:
        prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
        if not prefs:
            prefs = UserPreferences(user_id=user_id)
            db.add(prefs)
            is_new_user = True
        else:
            is_new_user = False
        
        # Reset conversation state
        prefs.conversation_state = ""
        prefs.buffer_mode = False
    
    welcome_text = (
        f"👋 <b>Bienvenue {user.first_name}!</b>\n\n"
        "🤖 <b>Bot de Messagerie Avancé v2.0</b>\n\n"
        "✨ <b>Fonctionnalités:</b>\n"
        "• 📝 Ajout de préfixe/suffixe automatique\n"
        "• 🔄 Remplacement de mots-clés intelligent\n"
        "• 📢 Publication automatique vers canal\n"
        "• ⚡ Traitement massif (100+ messages)\n"
        "• 📊 Statistiques détaillées\n\n"
        "💡 <b>Commandes rapides:</b>\n"
        "/start - Afficher ce menu\n"
        "/stats - Voir vos statistiques\n"
        "/reset - Tout réinitialiser\n\n"
        "📋 <b>Sélectionnez une option ci-dessous:</b>"
    )
    
    try:
        await update.message.reply_photo(
            photo=WELCOME_IMAGE,
            caption=welcome_text,
            reply_markup=get_main_menu(show_tutorial=is_new_user),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Erreur envoi image: {e}")
        await update.message.reply_text(
            welcome_text,
            reply_markup=get_main_menu(show_tutorial=is_new_user),
            parse_mode="HTML"
        )
    
    update_user_activity(user_id)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestionnaire universel pour tous les boutons inline"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    # Ignorer les boutons non-op
    if data == "noop":
        return
    
    with get_db() as db:
        prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
        if not prefs:
            prefs = UserPreferences(user_id=user_id)
            db.add(prefs)
            db.flush()
        
        # Navigation dans les menus
        if data == "menu_main":
            prefs.conversation_state = ""
            text = "📋 <b>Menu Principal</b>\n\nSélectionnez une option:"
            await safe_edit_message(query, text, get_main_menu(), parse_mode="HTML")
        
        elif data == "menu_keyword":
            text = "🔄 <b>Remplacement de Mots-clés</b>\n\n"
            if prefs.keyword_find:
                text += f"🔍 Chercher: <code>{prefs.keyword_find}</code>\n"
                text += f"✨ Remplacer par: <code>{prefs.keyword_replace}</code>\n\n"
                text += "Chaque occurrence sera remplacée automatiquement."
            else:
                text += "Aucun remplacement défini."
            await safe_edit_message(query, text, get_keyword_menu(prefs.keyword_find, prefs.keyword_replace), parse_mode="HTML")
        
        elif data == "menu_publish":
            text = "📢 <b>Mode Publication</b>\n\n"
            if prefs.publish_mode:
                text += f"✅ <b>Activé</b>\n"
                text += f"📍 Canal: <code>{prefs.target_chat_id}</code>\n\n"
                text += "Vos messages seront publiés dans le canal."
            else:
                text += "❌ <b>Désactivé</b>\n\n"
                text += "Activez ce mode pour publier automatiquement."
            await safe_edit_message(query, text, get_publish_menu(prefs.publish_mode, str(prefs.target_chat_id) if prefs.target_chat_id else ""), parse_mode="HTML")
        
        elif data == "menu_bulk":
            buffer_count = len(get_buffer_messages(user_id))
            text = "⚡ <b>Traitement Massif</b>\n\n"
            if prefs.buffer_mode:
                text += f"🟢 Mode actif\n"
                text += f"📊 {buffer_count} messages en attente\n\n"
                text += "Envoyez vos messages, ils seront bufferisés."
            else:
                text += "⚪ Mode inactif\n\n"
                text += "Activez pour accumuler des messages avant traitement."
            await safe_edit_message(query, text, get_bulk_menu(prefs.buffer_mode, buffer_count), parse_mode="HTML")
        
        elif data == "menu_stats":
            text = "📊 <b>Vos Statistiques</b>\n\n"
            text += f"👤 User ID: <code>{user_id}</code>\n"
            text += f"📅 Membre depuis: {prefs.created_at.strftime('%d/%m/%Y')}\n"
            text += f"🕐 Dernière activité: {prefs.last_activity.strftime('%d/%m/%Y %H:%M')}\n\n"
            text += f"📈 Messages traités: <b>{prefs.messages_processed}</b>\n"
            text += f"❌ Échecs: <b>{prefs.messages_failed}</b>\n\n"
            
            success_rate = 0
            if prefs.messages_processed + prefs.messages_failed > 0:
                success_rate = (prefs.messages_processed / (prefs.messages_processed + prefs.messages_failed)) * 100
            text += f"✅ Taux de réussite: <b>{success_rate:.1f}%</b>"
            await safe_edit_message(query, text, get_main_menu(), parse_mode="HTML")
        
        elif data == "menu_status":
            text = "ℹ️ <b>État de vos paramètres</b>\n\n"
            text += f"📝 Préfixe: <code>{prefs.prefix or '(vide)'}</code>\n"
            text += f"📌 Suffixe: <code>{prefs.suffix or '(vide)'}</code>\n"
            text += f"🔍 Chercher: <code>{prefs.keyword_find or '(vide)'}</code>\n"
            text += f"✨ Remplacer par: <code>{prefs.keyword_replace or '(vide)'}</code>\n"
            text += f"📢 Publication: {'✅ Activé' if prefs.publish_mode else '❌ Désactivé'}\n"
            if prefs.target_chat_id:
                text += f"📍 Canal: <code>{prefs.target_chat_id}</code>\n"
            text += f"⚡ Buffer: {'🟢 Actif' if prefs.buffer_mode else '⚪ Inactif'}"
            await safe_edit_message(query, text, get_main_menu(), parse_mode="HTML")
        
        elif data == "menu_reset":
            text = "⚠️ <b>Réinitialisation Complète</b>\n\n"
            text += "Cette action va supprimer:\n"
            text += "• Tous vos paramètres\n"
            text += "• Votre buffer de messages\n"
            text += "• Vos statistiques ne seront PAS effacées\n\n"
            text += "<b>Cette action est irréversible!</b>"
            await safe_edit_message(query, text, get_confirm_reset_keyboard(), parse_mode="HTML")
        
        elif data == "confirm_reset":
            prefs.prefix = ""
            prefs.suffix = ""
            prefs.keyword_find = ""
            prefs.keyword_replace = ""
            prefs.publish_mode = False
            prefs.target_chat_id = None
            prefs.buffer_mode = False
            prefs.conversation_state = ""
            clear_buffer(user_id)
            
            text = "✅ <b>Réinitialisation réussie!</b>\n\n"
            text += "Tous vos paramètres ont été supprimés.\n"
            text += "Vos statistiques sont conservées."
            await safe_edit_message(query, text, get_main_menu(), parse_mode="HTML")
        
        # Actions de définition
        elif data == "set_prefix":
            prefs.conversation_state = WAITING_PREFIX
            text = "✏️ <b>Définir le préfixe</b>\n\n"
            text += "Envoyez le texte à utiliser comme préfixe.\n"
            text += "Exemple: <code>[PROMO] </code>"
            await safe_edit_message(query, text, get_cancel_keyboard(), parse_mode="HTML")
        
        elif data == "set_suffix":
            prefs.conversation_state = WAITING_SUFFIX
            text = "✏️ <b>Définir le suffixe</b>\n\n"
            text += "Envoyez le texte à utiliser comme suffixe.\n"
            text += "Exemple: <code> - Urgent!</code>"
            await safe_edit_message(query, text, get_cancel_keyboard(), parse_mode="HTML")
        
        elif data == "set_keyword_find":
            prefs.conversation_state = WAITING_KEYWORD_FIND
            text = "🔍 <b>Mot à remplacer</b>\n\n"
            text += "Envoyez le mot ou phrase à détecter.\n"
            text += "Exemple: <code>prix</code>"
            await safe_edit_message(query, text, get_cancel_keyboard(), parse_mode="HTML")
        
        elif data == "set_keyword_replace":
            prefs.conversation_state = WAITING_KEYWORD_REPLACE
            text = "✨ <b>Texte de remplacement</b>\n\n"
            text += "Envoyez le texte qui remplacera le mot-clé.\n"
            text += "Exemple: <code>tarif exclusif</code>"
            await safe_edit_message(query, text, get_cancel_keyboard(), parse_mode="HTML")
        
        elif data == "set_target_chat":
            prefs.conversation_state = WAITING_TARGET_CHAT
            text = "📍 <b>Définir le canal cible</b>\n\n"
            text += "Envoyez l'ID du canal/groupe.\n"
            text += "Exemple: <code>-1001234567890</code>\n\n"
            text += "💡 <b>Comment obtenir l'ID:</b>\n"
            text += "1. Ajoutez @userinfobot à votre canal\n"
            text += "2. Forwardez un message du canal\n"
            text += "3. Le bot vous donnera l'ID"
            await safe_edit_message(query, text, get_cancel_keyboard(), parse_mode="HTML")
        
        # Actions de suppression
        elif data == "clear_prefix":
            prefs.prefix = ""
            text = "✅ <b>Préfixe supprimé</b>"
            await safe_edit_message(query, text, get_prefix_menu(""), parse_mode="HTML")
        
        elif data == "clear_suffix":
            prefs.suffix = ""
            text = "✅ <b>Suffixe supprimé</b>"
            await safe_edit_message(query, text, get_suffix_menu(""), parse_mode="HTML")
        
        elif data == "clear_keyword":
            prefs.keyword_find = ""
            prefs.keyword_replace = ""
            text = "✅ <b>Remplacement supprimé</b>"
            await safe_edit_message(query, text, get_keyword_menu("", ""), parse_mode="HTML")
        
        # Toggle actions
        elif data == "toggle_publish":
            prefs.publish_mode = not prefs.publish_mode
            status = "activé ✅" if prefs.publish_mode else "désactivé ❌"
            
            if prefs.publish_mode and not prefs.target_chat_id:
                text = "⚠️ <b>Attention!</b>\n\nMode publication activé mais aucun canal cible défini.\n\nVeuillez définir un canal."
            else:
                text = f"📢 <b>Mode publication {status}</b>"
            
            await safe_edit_message(query, text, get_publish_menu(prefs.publish_mode, str(prefs.target_chat_id) if prefs.target_chat_id else ""), parse_mode="HTML")
        
        elif data == "toggle_bulk":
            prefs.buffer_mode = not prefs.buffer_mode
            
            if not prefs.buffer_mode:
                clear_buffer(user_id)
            
            buffer_count = len(get_buffer_messages(user_id))
            status = "activé 🟢" if prefs.buffer_mode else "désactivé ⚪"
            text = f"⚡ <b>Mode buffer {status}</b>\n\n"
            
            if prefs.buffer_mode:
                text += "Envoyez vos messages, ils seront bufferisés.\n"
                text += "Revenez ici pour les traiter tous ensemble."
            else:
                text += "Les nouveaux messages seront traités normalement."
            
            await safe_edit_message(query, text, get_bulk_menu(prefs.buffer_mode, buffer_count), parse_mode="HTML")
        
        elif data == "clear_bulk":
            clear_buffer(user_id)
            text = "✅ <b>Buffer vidé</b>\n\nTous les messages en attente ont été supprimés."
            await safe_edit_message(query, text, get_bulk_menu(prefs.buffer_mode, 0), parse_mode="HTML")
        
        elif data == "process_bulk":
            messages = get_buffer_messages(user_id)
            
            if not messages:
                text = "❌ <b>Aucun message à traiter</b>"
                await safe_edit_message(query, text, get_bulk_menu(prefs.buffer_mode, 0), parse_mode="HTML")
                return
            
            # Envoyer un message de statut
            status_msg = await query.message.reply_text(
                f"⚙️ <b>Traitement de {len(messages)} messages...</b>\n\nInitialisation...",
                parse_mode="HTML"
            )
            
            # Traiter les messages
            result = await handle_bulk_processing(
                messages=messages,
                prefs=prefs,
                bot=context.bot,
                status_message=status_msg
            )
            
            # Mettre à jour les statistiques
            prefs.messages_processed += result.get('successful', 0)
            prefs.messages_failed += result.get('failed', 0)
            
            # Vider le buffer
            clear_buffer(user_id)
            prefs.buffer_mode = False
            
            # Message final
            await status_msg.edit_text(
                f"✅ <b>Traitement terminé!</b>\n\n"
                f"📊 Total: {result['total']}\n"
                f"✅ Réussis: {result['successful']}\n"
                f"❌ Échecs: {result['failed']}\n"
                f"⏭️ Ignorés: {result.get('skipped', 0)}\n\n"
                f"Mode buffer désactivé automatiquement.",
                parse_mode="HTML"
            )
        
        elif data == "test_publish":
            if not prefs.target_chat_id:
                text = "❌ <b>Aucun canal cible défini</b>\n\nVeuillez d'abord définir un canal."
                await safe_edit_message(query, text, get_publish_menu(prefs.publish_mode, ""), parse_mode="HTML")
                return
            
            test_message = f"🧪 Test du bot\nUtilisateur: {user_id}\nHeure: {prefs.last_activity.strftime('%H:%M:%S')}"
            
            try:
                await context.bot.send_message(
                    chat_id=prefs.target_chat_id,
                    text=test_message
                )
                text = "✅ <b>Test réussi!</b>\n\nLe message a été envoyé au canal."
                await safe_edit_message(query, text, get_test_result_keyboard(), parse_mode="HTML")
            except TelegramError as e:
                text = f"❌ <b>Échec du test</b>\n\nErreur: {str(e)}\n\nVérifiez que:\n• L'ID est correct\n• Le bot est administrateur"
                await safe_edit_message(query, text, get_test_result_keyboard(), parse_mode="HTML")
        
        elif data.startswith("tutorial_"):
            page = int(data.split("_")[1])
            await show_tutorial(query, page)
        
        elif data == "show_tutorial":
            await show_tutorial(query, 1)
        
        elif data == "menu_prefix":
            text = "📝 <b>Gestion du Préfixe</b>\n\n"
            text += f"<i>Actuel:</i> <code>{prefs.prefix or '(vide)'}</code>\n\n"
            text += "Le préfixe est ajouté au début de chaque message."
            await safe_edit_message(query, text, get_prefix_menu(prefs.prefix), parse_mode="HTML")
        
        elif data == "menu_suffix":
            text = "📌 <b>Gestion du Suffixe</b>\n\n"
            text += f"<i>Actuel:</i> <code>{prefs.suffix or '(vide)'}</code>\n\n"
            text += "Le suffixe est ajouté à la fin de chaque message."
            await safe_edit_message(query, text, get_suffix_menu(prefs.suffix), parse_mode="HTML")
    
    update_user_activity(user_id)


async def handle_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    HANDLER UNIVERSEL : Gère TOUS les types de messages Telegram
    - Texte pur
    - Photos, vidéos, documents, audio, voice, animations, stickers
    - Avec ou sans légende/caption
    - Détection automatique du contexte (conversation state, buffer mode, etc.)
    """
    user_id = update.effective_user.id
    message = update.message
    
    # === ÉTAPE 1: EXTRACTION DES DONNÉES ===
    original_text = ""
    has_media = False
    media_type = None
    media_file_id = None
    
    # 1.A - Texte pur
    if message.text:
        original_text = message.text
        media_type = "text"
    
    # 1.B - Médias avec légende
    elif message.caption:
        original_text = message.caption
        has_media = True
        
        if message.photo:
            media_type = "photo"
            media_file_id = message.photo[-1].file_id
        elif message.video:
            media_type = "video"
            media_file_id = message.video.file_id
        elif message.document:
            media_type = "document"
            media_file_id = message.document.file_id
        elif message.audio:
            media_type = "audio"
            media_file_id = message.audio.file_id
        elif message.voice:
            media_type = "voice"
            media_file_id = message.voice.file_id
        elif message.animation:
            media_type = "animation"
            media_file_id = message.animation.file_id
        elif message.sticker:
            media_type = "sticker"
            media_file_id = message.sticker.file_id
    
    # 1.C - Médias SANS légende (générer des descriptions)
    else:
        has_media = True
        
        if message.photo:
            original_text = "[Photo sans légende]"
            media_type = "photo"
            media_file_id = message.photo[-1].file_id
        elif message.video:
            original_text = "[Vidéo sans légende]"
            media_type = "video"
            media_file_id = message.video.file_id
        elif message.document:
            original_text = f"[Document: {message.document.file_name or 'sans nom'}]"
            media_type = "document"
            media_file_id = message.document.file_id
        elif message.audio:
            original_text = f"[Audio: {message.audio.title or 'sans titre'}]"
            media_type = "audio"
            media_file_id = message.audio.file_id
        elif message.voice:
            original_text = "[Message vocal]"
            media_type = "voice"
            media_file_id = message.voice.file_id
        elif message.contact:
            original_text = f"[Contact: {message.contact.first_name or 'Inconnu'}]"
            media_type = "contact"
        elif message.location:
            original_text = "[Position géographique]"
            media_type = "location"
        elif message.sticker:
            original_text = "[Sticker]"
            media_type = "sticker"
            media_file_id = message.sticker.file_id
        elif message.animation:
            original_text = "[Animation]"
            media_type = "animation"
            media_file_id = message.animation.file_id
        else:
            original_text = "[Message non pris en charge]"
            media_type = "unknown"
    
    # === ÉTAPE 2: RÉCUPÉRATION DES PRÉFÉRENCES ===
    with get_db() as db:
        prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
        if not prefs:
            prefs = UserPreferences(user_id=user_id)
            db.add(prefs)
            db.flush()
        
        conversation_state = prefs.conversation_state or ""
        
        # === ÉTAPE 3: GESTION DES ÉTATS DE CONVERSATION ===
        # Si on attend une entrée spécifique (définition de paramètre)
        if conversation_state in [WAITING_PREFIX, WAITING_SUFFIX, WAITING_KEYWORD_FIND, 
                                  WAITING_KEYWORD_REPLACE, WAITING_TARGET_CHAT]:
            
            # Seul le texte pur est accepté pour les paramètres
            if media_type != "text":
                await update.message.reply_text(
                    "❌ <b>Texte requis</b>\n\n"
                    "Veuillez envoyer uniquement du texte pour cette étape.",
                    parse_mode="HTML"
                )
                return
            
            # Traiter selon l'état
            if conversation_state == WAITING_PREFIX:
                prefs.prefix = original_text
                prefs.conversation_state = ""
                await update.message.reply_text(
                    f"✅ <b>Préfixe défini:</b>\n<code>{original_text}</code>\n\n"
                    "Tous vos messages commenceront par ce texte.",
                    parse_mode="HTML"
                )
            
            elif conversation_state == WAITING_SUFFIX:
                prefs.suffix = original_text
                prefs.conversation_state = ""
                await update.message.reply_text(
                    f"✅ <b>Suffixe défini:</b>\n<code>{original_text}</code>\n\n"
                    "Tous vos messages se termineront par ce texte.",
                    parse_mode="HTML"
                )
            
            elif conversation_state == WAITING_KEYWORD_FIND:
                prefs.keyword_find = original_text
                prefs.conversation_state = ""
                await update.message.reply_text(
                    f"✅ <b>Mot-clé défini:</b>\n<code>{original_text}</code>\n\n"
                    "Toutes les occurrences seront remplacées.",
                    parse_mode="HTML"
                )
            
            elif conversation_state == WAITING_KEYWORD_REPLACE:
                prefs.keyword_replace = original_text
                prefs.conversation_state = ""
                await update.message.reply_text(
                    f"✅ <b>Remplacement défini:</b>\n<code>{original_text}</code>\n\n"
                    "Le mot-clé sera remplacé par ce texte.",
                    parse_mode="HTML"
                )
            
            elif conversation_state == WAITING_TARGET_CHAT:
                chat_id = validate_chat_id(original_text)
                if chat_id:
                    prefs.target_chat_id = chat_id
                    prefs.conversation_state = ""
                    await update.message.reply_text(
                        f"✅ <b>Canal cible défini:</b>\n<code>{chat_id}</code>\n\n"
                        "💡 Testez avec le bouton 'Tester l'envoi' dans le menu.",
                        parse_mode="HTML"
                    )
                else:
                    await update.message.reply_text(
                        "❌ <b>ID invalide</b>\n\n"
                        "L'ID doit être un nombre (généralement négatif pour les groupes).\n"
                        "Exemple: <code>-1001234567890</code>",
                        parse_mode="HTML"
                    )
            
            update_user_activity(user_id)
            return
        
        # === ÉTAPE 4: MODE BUFFER ===
        if prefs.buffer_mode:
            # Seuls les messages avec texte/caption sont acceptés en buffer
            if media_type in ["text", "photo", "video", "document", "audio", "voice", "animation"]:
                add_to_buffer(user_id, original_text)
                buffer_count = len(get_buffer_messages(user_id))
                
                if buffer_count >= 100:
                    await update.message.reply_text(
                        "⚠️ <b>Limite atteinte!</b>\n\n"
                        f"Vous avez 100 messages en attente.\n"
                        "Retournez au menu pour les traiter.",
                        parse_mode="HTML"
                    )
                else:
                    await update.message.reply_text(
                        f"✅ Message {buffer_count}/100 ajouté au buffer"
                    )
            else:
                await update.message.reply_text(
                    "❌ <b>Type non supporté en mode buffer</b>\n\n"
                    "Seuls les messages avec du texte ou des légendes sont acceptés.",
                    parse_mode="HTML"
                )
            
            update_user_activity(user_id)
            return
        
        # === ÉTAPE 5: TRAITEMENT NORMAL ===
        await process_message_with_transformations(
            update=update,
            context=context,
            prefs=prefs,
            original_text=original_text,
            media_type=media_type,
            media_file_id=media_file_id,
            has_media=has_media
        )


async def process_message_with_transformations(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    prefs: UserPreferences,
    original_text: str,
    media_type: str,
    media_file_id: str = None,
    has_media: bool = False
):
    """
    Applique toutes les transformations et publie/répond selon la config
    """
    # === TRANSFORMATIONS DU TEXTE ===
    processed_text = original_text
    
    # 1. Remplacement de mots-clés
    if prefs.keyword_find and prefs.keyword_replace:
        processed_text = processed_text.replace(prefs.keyword_find, prefs.keyword_replace)
    
    # 2. Ajout préfixe/suffixe
    processed_text = f"{prefs.prefix or ''}{processed_text}{prefs.suffix or ''}"
    
    # 3. Limite Telegram (4096 caractères)
    if len(processed_text) > 4096:
        processed_text = processed_text[:4093] + "..."
    
    # === PUBLICATION / RÉPONSE ===
    try:
        # MODE PUBLICATION vers un canal
        if prefs.publish_mode and prefs.target_chat_id:
            await send_message_to_target(
                bot=context.bot,
                chat_id=prefs.target_chat_id,
                text=processed_text,
                media_type=media_type,
                media_file_id=media_file_id
            )
            
            await update.message.reply_text("✅ Message publié dans le canal!")
            
            # Incrémenter compteur succès
            with get_db() as db:
                user_prefs = db.query(UserPreferences).filter(
                    UserPreferences.user_id == prefs.user_id
                ).first()
                if user_prefs:
                    user_prefs.messages_processed += 1
        
        # MODE NORMAL (réponse dans le chat privé)
        else:
            await send_message_to_target(
                bot=context.bot,
                chat_id=update.effective_chat.id,
                text=processed_text,
                media_type=media_type,
                media_file_id=media_file_id,
                reply_to=update.message.message_id
            )
            
            # Incrémenter compteur succès
            with get_db() as db:
                user_prefs = db.query(UserPreferences).filter(
                    UserPreferences.user_id == prefs.user_id
                ).first()
                if user_prefs:
                    user_prefs.messages_processed += 1
    
    except TelegramError as e:
        logger.error(f"Erreur envoi message: {e}")
        
        await update.message.reply_text(
            f"❌ <b>Erreur:</b>\n{str(e)}\n\n"
            "Vérifiez que le bot a les permissions nécessaires.",
            parse_mode="HTML"
        )
        
        # Incrémenter compteur échecs
        with get_db() as db:
            user_prefs = db.query(UserPreferences).filter(
                UserPreferences.user_id == prefs.user_id
            ).first()
            if user_prefs:
                user_prefs.messages_failed += 1
    
    update_user_activity(prefs.user_id)


async def send_message_to_target(
    bot,
    chat_id: int,
    text: str,
    media_type: str,
    media_file_id: str = None,
    reply_to: int = None
):
    """
    Envoie un message (texte ou média) vers le chat cible
    Gère tous les types de médias supportés par Telegram
    """
    send_kwargs = {"chat_id": chat_id}
    if reply_to:
        send_kwargs["reply_to_message_id"] = reply_to
    
    if media_type == "text":
        await bot.send_message(text=text, **send_kwargs)
    
    elif media_type == "photo" and media_file_id:
        await bot.send_photo(photo=media_file_id, caption=text, **send_kwargs)
    
    elif media_type == "video" and media_file_id:
        await bot.send_video(video=media_file_id, caption=text, **send_kwargs)
    
    elif media_type == "document" and media_file_id:
        await bot.send_document(document=media_file_id, caption=text, **send_kwargs)
    
    elif media_type == "audio" and media_file_id:
        await bot.send_audio(audio=media_file_id, caption=text, **send_kwargs)
    
    elif media_type == "voice" and media_file_id:
        await bot.send_voice(voice=media_file_id, caption=text, **send_kwargs)
    
    elif media_type == "animation" and media_file_id:
        await bot.send_animation(animation=media_file_id, caption=text, **send_kwargs)
    
    elif media_type == "sticker" and media_file_id:
        # Les stickers ne supportent pas de caption
        await bot.send_sticker(sticker=media_file_id, **send_kwargs)
        # Envoyer le texte séparément si nécessaire
        if text and text != "[Sticker]":
            await bot.send_message(text=text, chat_id=chat_id)
    
    else:
        # Fallback: envoyer juste le texte
        await bot.send_message(text=text, **send_kwargs)


async def safe_edit_message(query, text: str, markup, **kwargs):
    """Édite un message de manière sécurisée (caption ou texte)"""
    try:
        await query.edit_message_caption(
            caption=text,
            reply_markup=markup,
            **kwargs
        )
    except:
        try:
            await query.edit_message_text(
                text=text,
                reply_markup=markup,
                **kwargs
            )
        except Exception as e:
            logger.error(f"Erreur édition message: {e}")


async def show_tutorial(query, page: int):
    """Affiche le tutoriel page par page"""
    tutorials = {
        1: (
            "📖 <b>Tutoriel - Page 1/5</b>\n\n"
            "<b>🎯 Préfixe et Suffixe</b>\n\n"
            "Le préfixe est ajouté au début de vos messages.\n"
            "Le suffixe à la fin.\n\n"
            "<b>Exemple:</b>\n"
            "Préfixe: <code>[PROMO] </code>\n"
            "Suffixe: <code> - Offre limitée!</code>\n\n"
            "Message: <code>Nouveau produit</code>\n"
            "Résultat: <code>[PROMO] Nouveau produit - Offre limitée!</code>"
        ),
        2: (
            "📖 <b>Tutoriel - Page 2/5</b>\n\n"
            "<b>🔄 Remplacement de Mots-clés</b>\n\n"
            "Remplacez automatiquement des mots ou phrases.\n\n"
            "<b>Exemple:</b>\n"
            "Chercher: <code>acheter</code>\n"
            "Remplacer: <code>réserver maintenant</code>\n\n"
            "Message: <code>Venez acheter ce produit</code>\n"
            "Résultat: <code>Venez réserver maintenant ce produit</code>"
        ),
        3: (
            "📖 <b>Tutoriel - Page 3/5</b>\n\n"
            "<b>📢 Mode Publication</b>\n\n"
            "Publiez automatiquement dans un canal/groupe.\n\n"
            "<b>Étapes:</b>\n"
            "1. Obtenez l'ID du canal (avec @userinfobot)\n"
            "2. Définissez le canal cible\n"
            "3. Ajoutez le bot comme administrateur\n"
            "4. Activez le mode publication\n"
            "5. Testez l'envoi\n\n"
            "Vos messages seront publiés automatiquement!"
        ),
        4: (
            "📖 <b>Tutoriel - Page 4/5</b>\n\n"
            "<b>⚡ Traitement Massif</b>\n\n"
            "Traitez jusqu'à 100 messages d'un coup!\n\n"
            "<b>Utilisation:</b>\n"
            "1. Activez le mode buffer\n"
            "2. Envoyez vos messages (jusqu'à 100)\n"
            "3. Cliquez sur 'Traiter tout'\n"
            "4. Le bot traite tout en parallèle\n\n"
            "Parfait pour les envois massifs!"
        ),
        5: (
            "📖 <b>Tutoriel - Page 5/5</b>\n\n"
            "<b>💡 Astuces Avancées</b>\n\n"
            "• Combinez plusieurs transformations\n"
            "• Vérifiez vos stats régulièrement\n"
            "• Testez avant d'envoyer en masse\n"
            "• Le bot gère les rate limits automatiquement\n"
            "• Utilisez /reset pour recommencer\n\n"
            "<b>Besoin d'aide?</b>\n"
            "Utilisez /start pour revenir au menu principal!"
        )
    }
    
    text = tutorials.get(page, tutorials[1])
    await safe_edit_message(query, text, get_tutorial_navigation(page, 5), parse_mode="HTML")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /stats rapide"""
    user_id = update.effective_user.id
    
    with get_db() as db:
        prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
        
        if not prefs:
            await update.message.reply_text("❌ Aucune donnée disponible. Utilisez /start pour commencer.")
            return
        
        success_rate = 0
        if prefs.messages_processed + prefs.messages_failed > 0:
            success_rate = (prefs.messages_processed / (prefs.messages_processed + prefs.messages_failed)) * 100
        
        text = (
            "📊 <b>Vos Statistiques</b>\n\n"
            f"📈 Messages traités: <b>{prefs.messages_processed}</b>\n"
            f"❌ Échecs: <b>{prefs.messages_failed}</b>\n"
            f"✅ Taux de réussite: <b>{success_rate:.1f}%</b>\n\n"
            f"📅 Membre depuis: {prefs.created_at.strftime('%d/%m/%Y')}\n"
            f"🕐 Dernière activité: {prefs.last_activity.strftime('%d/%m/%Y %H:%M')}"
        )
        
        await update.message.reply_text(text, parse_mode="HTML")
    
    update_user_activity(user_id)


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /reset rapide"""
    user_id = update.effective_user.id
    
    with get_db() as db:
        prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
        if prefs:
            prefs.prefix = ""
            prefs.suffix = ""
            prefs.keyword_find = ""
            prefs.keyword_replace = ""
            prefs.publish_mode = False
            prefs.target_chat_id = None
            prefs.buffer_mode = False
            prefs.conversation_state = ""
    
    clear_buffer(user_id)
    
    await update.message.reply_text(
        "✅ <b>Réinitialisation réussie!</b>\n\n"
        "Tous vos paramètres ont été supprimés.\n"
        "Utilisez /start pour recommencer.",
        parse_mode="HTML"
    )
    
    update_user_activity(user_id)