from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_main_menu(show_tutorial: bool = False):
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
            InlineKeyboardButton("⚡ Traitement Massif", callback_data="menu_bulk"),
        ],
        [
            InlineKeyboardButton("📊 Statistiques", callback_data="menu_stats"),
            InlineKeyboardButton("ℹ️ État", callback_data="menu_status")
        ],
        [
            InlineKeyboardButton("🔄 Réinitialiser", callback_data="menu_reset")
        ]
    ]
    
    if show_tutorial:
        keyboard.append([InlineKeyboardButton("📖 Tutoriel", callback_data="show_tutorial")])
    
    return InlineKeyboardMarkup(keyboard)


def get_prefix_menu(current_value: str = ""):
    """Menu pour gérer le préfixe"""
    status = f"Actuel: {current_value[:20]}..." if current_value else "Non défini"
    keyboard = [
        [InlineKeyboardButton(f"📝 {status}", callback_data="noop")],
        [InlineKeyboardButton("✏️ Définir préfixe", callback_data="set_prefix")],
        [InlineKeyboardButton("🗑️ Supprimer", callback_data="clear_prefix")],
        [InlineKeyboardButton("◀️ Retour", callback_data="menu_main")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_suffix_menu(current_value: str = ""):
    """Menu pour gérer le suffixe"""
    status = f"Actuel: {current_value[:20]}..." if current_value else "Non défini"
    keyboard = [
        [InlineKeyboardButton(f"📌 {status}", callback_data="noop")],
        [InlineKeyboardButton("✏️ Définir suffixe", callback_data="set_suffix")],
        [InlineKeyboardButton("🗑️ Supprimer", callback_data="clear_suffix")],
        [InlineKeyboardButton("◀️ Retour", callback_data="menu_main")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_keyword_menu(find_value: str = "", replace_value: str = ""):
    """Menu pour gérer les remplacements de mots-clés"""
    status_find = f"Chercher: {find_value[:15]}..." if find_value else "Non défini"
    status_replace = f"→ {replace_value[:15]}..." if replace_value else "Non défini"
    
    keyboard = [
        [InlineKeyboardButton(f"🔍 {status_find}", callback_data="noop")],
        [InlineKeyboardButton(f"✨ {status_replace}", callback_data="noop")],
        [InlineKeyboardButton("🔍 Définir mot à remplacer", callback_data="set_keyword_find")],
        [InlineKeyboardButton("✨ Définir remplacement", callback_data="set_keyword_replace")],
        [InlineKeyboardButton("🗑️ Tout supprimer", callback_data="clear_keyword")],
        [InlineKeyboardButton("◀️ Retour", callback_data="menu_main")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_publish_menu(is_active: bool, target_chat: str = ""):
    """Menu pour gérer le mode publication"""
    status_emoji = "✅" if is_active else "❌"
    toggle_text = "Désactiver" if is_active else "Activer"
    target_status = f"Canal: {target_chat}" if target_chat else "Aucun canal défini"
    
    keyboard = [
        [InlineKeyboardButton(f"{status_emoji} État: {'Actif' if is_active else 'Inactif'}", callback_data="noop")],
        [InlineKeyboardButton(f"📍 {target_status}", callback_data="noop")],
        [InlineKeyboardButton(f"{status_emoji} {toggle_text}", callback_data="toggle_publish")],
        [InlineKeyboardButton("📍 Définir canal cible", callback_data="set_target_chat")],
        [InlineKeyboardButton("🧪 Tester l'envoi", callback_data="test_publish")],
        [InlineKeyboardButton("◀️ Retour", callback_data="menu_main")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_bulk_menu(buffer_mode: bool, buffer_count: int = 0):
    """Menu pour le traitement massif"""
    status = "🟢 Actif" if buffer_mode else "⚪ Inactif"
    
    keyboard = [
        [InlineKeyboardButton(f"⚡ Mode: {status}", callback_data="noop")],
        [InlineKeyboardButton(f"📊 Messages en attente: {buffer_count}", callback_data="noop")],
    ]
    
    if buffer_mode:
        keyboard.append([
            InlineKeyboardButton("✅ Traiter tout", callback_data="process_bulk"),
            InlineKeyboardButton("🗑️ Vider", callback_data="clear_bulk")
        ])
        keyboard.append([InlineKeyboardButton("⏸️ Désactiver mode", callback_data="toggle_bulk")])
    else:
        keyboard.append([InlineKeyboardButton("▶️ Activer mode", callback_data="toggle_bulk")])
    
    keyboard.append([InlineKeyboardButton("◀️ Retour", callback_data="menu_main")])
    return InlineKeyboardMarkup(keyboard)


def get_cancel_keyboard():
    """Bouton d'annulation simple"""
    keyboard = [[InlineKeyboardButton("❌ Annuler", callback_data="menu_main")]]
    return InlineKeyboardMarkup(keyboard)


def get_confirm_reset_keyboard():
    """Confirmation de réinitialisation"""
    keyboard = [
        [InlineKeyboardButton("⚠️ Confirmer la réinitialisation", callback_data="noop")],
        [
            InlineKeyboardButton("✅ Oui, tout effacer", callback_data="confirm_reset"),
        ],
        [
            InlineKeyboardButton("❌ Non, annuler", callback_data="menu_main")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_tutorial_navigation(page: int = 1, total_pages: int = 5):
    """Navigation pour le tutoriel"""
    keyboard = []
    
    # Navigation
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("◀️ Précédent", callback_data=f"tutorial_{page-1}"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("Suivant ▶️", callback_data=f"tutorial_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton(f"📄 Page {page}/{total_pages}", callback_data="noop")])
    keyboard.append([InlineKeyboardButton("◀️ Menu principal", callback_data="menu_main")])
    
    return InlineKeyboardMarkup(keyboard)


def get_test_result_keyboard():
    """Clavier après un test"""
    keyboard = [
        [InlineKeyboardButton("🔄 Tester à nouveau", callback_data="test_publish")],
        [InlineKeyboardButton("◀️ Retour", callback_data="menu_publish")]
    ]
    return InlineKeyboardMarkup(keyboard)