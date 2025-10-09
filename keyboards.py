from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_main_menu():
    """Menu principal avec toutes les options"""
    keyboard = [
        [
            InlineKeyboardButton("📝 Préfixe", callback_data="menu_prefix"),
            InlineKeyboardButton("📌 Suffixe", callback_data="menu_suffix")
        ],
        [
            InlineKeyboardButton("🔄 Remplacement", callback_data="menu_keyword"),
        ],
        [
            InlineKeyboardButton("📢 Mode Publication", callback_data="menu_publish"),
        ],
        [
            InlineKeyboardButton("ℹ️ État", callback_data="menu_status"),
            InlineKeyboardButton("🔄 Réinitialiser", callback_data="menu_reset")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_prefix_menu():
    """Menu pour gérer le préfixe"""
    keyboard = [
        [InlineKeyboardButton("✏️ Définir préfixe", callback_data="set_prefix")],
        [InlineKeyboardButton("🗑️ Supprimer préfixe", callback_data="clear_prefix")],
        [InlineKeyboardButton("◀️ Retour", callback_data="menu_main")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_suffix_menu():
    """Menu pour gérer le suffixe"""
    keyboard = [
        [InlineKeyboardButton("✏️ Définir suffixe", callback_data="set_suffix")],
        [InlineKeyboardButton("🗑️ Supprimer suffixe", callback_data="clear_suffix")],
        [InlineKeyboardButton("◀️ Retour", callback_data="menu_main")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_keyword_menu():
    """Menu pour gérer les remplacements de mots-clés"""
    keyboard = [
        [InlineKeyboardButton("🔍 Définir mot à remplacer", callback_data="set_keyword_find")],
        [InlineKeyboardButton("✨ Définir remplacement", callback_data="set_keyword_replace")],
        [InlineKeyboardButton("🗑️ Supprimer remplacement", callback_data="clear_keyword")],
        [InlineKeyboardButton("◀️ Retour", callback_data="menu_main")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_publish_menu(is_active: bool):
    """Menu pour gérer le mode publication"""
    status_emoji = "✅" if is_active else "❌"
    toggle_text = "Désactiver" if is_active else "Activer"
    
    keyboard = [
        [InlineKeyboardButton(f"{status_emoji} {toggle_text} mode publication", 
                            callback_data="toggle_publish")],
        [InlineKeyboardButton("📍 Définir canal cible", callback_data="set_target_chat")],
        [InlineKeyboardButton("◀️ Retour", callback_data="menu_main")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_cancel_keyboard():
    """Bouton d'annulation simple"""
    keyboard = [[InlineKeyboardButton("❌ Annuler", callback_data="menu_main")]]
    return InlineKeyboardMarkup(keyboard)


def get_confirm_reset_keyboard():
    """Confirmation de réinitialisation"""
    keyboard = [
        [
            InlineKeyboardButton("✅ Oui, réinitialiser", callback_data="confirm_reset"),
            InlineKeyboardButton("❌ Non, annuler", callback_data="menu_main")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)