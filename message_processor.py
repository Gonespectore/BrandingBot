import asyncio
import logging
from typing import List, Dict, Optional, Callable
from telegram import Bot
from telegram.error import TelegramError, RetryAfter, TimedOut
from db import UserPreferences

logger = logging.getLogger(__name__)


class MessageProcessor:
    """Gestionnaire ultra-optimisé pour le traitement massif de messages"""
    
    def __init__(self, max_concurrent: int = 15, base_delay: float = 0.05):
        self.max_concurrent = max_concurrent
        self.base_delay = base_delay
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.processed_count = 0
        self.failed_count = 0
        self.total_messages = 0
        self.is_processing = False
    
    def reset_counters(self):
        """Réinitialise les compteurs"""
        self.processed_count = 0
        self.failed_count = 0
    
    async def process_single_message(
        self, 
        message_text: str, 
        prefs: UserPreferences,
        bot: Bot,
        retry_count: int = 3
    ) -> Dict:
        """
        Traite un message unique avec retry exponentiel
        
        Returns:
            Dict avec status, processed_text, et error si applicable
        """
        async with self.semaphore:
            try:
                # Validation
                if not message_text or not message_text.strip():
                    return {
                        "status": "skipped",
                        "reason": "Message vide"
                    }
                
                # Appliquer les transformations
                processed_text = message_text
                
                # Remplacement de mots-clés (support multi-occurrences)
                if prefs.keyword_find and prefs.keyword_replace:
                    processed_text = processed_text.replace(
                        prefs.keyword_find, 
                        prefs.keyword_replace
                    )
                
                # Ajout préfixe/suffixe
                processed_text = f"{prefs.prefix}{processed_text}{prefs.suffix}"
                
                # Validation de la longueur (Telegram limite à 4096 caractères)
                if len(processed_text) > 4096:
                    processed_text = processed_text[:4093] + "..."
                
                # Envoi du message avec retry exponentiel
                if prefs.publish_mode and prefs.target_chat_id:
                    attempt = 0
                    while attempt < retry_count:
                        try:
                            await bot.send_message(
                                chat_id=prefs.target_chat_id,
                                text=processed_text
                            )
                            
                            # Délai anti-rate-limit
                            await asyncio.sleep(self.base_delay)
                            
                            self.processed_count += 1
                            return {
                                "status": "success",
                                "processed_text": processed_text,
                                "original_text": message_text
                            }
                        
                        except RetryAfter as e:
                            # Telegram demande d'attendre
                            wait_time = e.retry_after + 2
                            logger.warning(f"Rate limit: attente de {wait_time}s")
                            await asyncio.sleep(wait_time)
                            attempt += 1
                        
                        except TimedOut:
                            # Timeout - retry avec délai exponentiel
                            wait_time = (2 ** attempt) * self.base_delay
                            logger.warning(f"Timeout: retry dans {wait_time}s")
                            await asyncio.sleep(wait_time)
                            attempt += 1
                        
                        except TelegramError as e:
                            error_msg = str(e).lower()
                            if any(x in error_msg for x in ["chat not found", "bot was blocked", "user is deactivated"]):
                                raise  # Ne pas retry si erreur permanente
                            
                            # Retry avec délai exponentiel
                            wait_time = (2 ** attempt) * self.base_delay
                            await asyncio.sleep(wait_time)
                            attempt += 1
                    
                    # Si tous les retries échouent
                    raise Exception(f"Échec après {retry_count} tentatives")
                
                else:
                    # Pas de mode publication - juste transformer
                    return {
                        "status": "transformed",
                        "processed_text": processed_text,
                        "original_text": message_text
                    }
            
            except Exception as e:
                self.failed_count += 1
                logger.error(f"Erreur traitement: {e}", exc_info=True)
                return {
                    "status": "error",
                    "error": str(e),
                    "original_text": message_text
                }
    
    async def process_batch(
        self,
        messages: List[str],
        prefs: UserPreferences,
        bot: Bot,
        progress_callback: Optional[Callable] = None
    ) -> Dict:
        """
        Traite un lot de messages en parallèle avec progression
        
        Args:
            messages: Liste des textes à traiter
            prefs: Préférences utilisateur
            bot: Instance du bot Telegram
            progress_callback: Fonction appelée pour chaque message traité
        
        Returns:
            Dict avec statistiques et résultats détaillés
        """
        self.reset_counters()
        self.total_messages = len(messages)
        self.is_processing = True
        
        if not messages:
            return {
                "status": "error",
                "error": "Aucun message à traiter"
            }
        
        # Validation des préférences
        if prefs.publish_mode and not prefs.target_chat_id:
            return {
                "status": "error",
                "error": "Mode publication activé mais aucun canal cible défini"
            }
        
        # Créer les tâches
        tasks = []
        for msg in messages:
            task = self.process_single_message(
                message_text=msg,
                prefs=prefs,
                bot=bot
            )
            tasks.append(task)
        
        # Exécuter en parallèle avec progression
        results = []
        completed = 0
        
        for task in asyncio.as_completed(tasks):
            result = await task
            results.append(result)
            completed += 1
            
            # Callback de progression
            if progress_callback:
                try:
                    await progress_callback(completed, self.total_messages, result)
                except Exception as e:
                    logger.error(f"Erreur callback progression: {e}")
        
        self.is_processing = False
        
        # Calculer les statistiques
        successful = sum(1 for r in results if r["status"] in ["success", "transformed"])
        failed = sum(1 for r in results if r["status"] == "error")
        skipped = sum(1 for r in results if r["status"] == "skipped")
        
        return {
            "status": "completed",
            "total": len(messages),
            "successful": successful,
            "failed": failed,
            "skipped": skipped,
            "results": results
        }
    
    def get_progress_percentage(self) -> float:
        """Retourne le pourcentage de progression"""
        if self.total_messages == 0:
            return 0.0
        return (self.processed_count + self.failed_count) / self.total_messages * 100


# Instance globale optimisée
message_processor = MessageProcessor(max_concurrent=15, base_delay=0.05)


async def handle_bulk_processing(
    messages: List[str],
    prefs: UserPreferences,
    bot: Bot,
    status_message=None
) -> Dict:
    """
    Helper pour le traitement bulk avec mise à jour du statut
    
    Args:
        messages: Liste des messages à traiter
        prefs: Préférences utilisateur
        bot: Instance du bot
        status_message: Message Telegram à mettre à jour
    
    Returns:
        Dict avec les résultats du traitement
    """
    last_update = 0
    
    async def update_progress(current: int, total: int, result: Dict):
        nonlocal last_update
        
        # Mise à jour tous les 3 messages ou si terminé
        if status_message and (current - last_update >= 3 or current == total):
            try:
                progress_pct = (current / total) * 100
                bar_length = 20
                filled = int(bar_length * current / total)
                bar = "▓" * filled + "░" * (bar_length - filled)
                
                status_emoji = "⚙️" if current < total else "✅"
                
                text = (
                    f"{status_emoji} <b>Traitement en cours...</b>\n\n"
                    f"[{bar}] {progress_pct:.1f}%\n"
                    f"📊 {current}/{total} messages\n\n"
                    f"✅ Réussis: {message_processor.processed_count}\n"
                    f"❌ Échecs: {message_processor.failed_count}"
                )
                
                await status_message.edit_text(text, parse_mode="HTML")
                last_update = current
            except Exception as e:
                logger.error(f"Erreur MAJ progression: {e}")
    
    result = await message_processor.process_batch(
        messages=messages,
        prefs=prefs,
        bot=bot,
        progress_callback=update_progress
    )
    
    return result


def validate_chat_id(chat_id_str: str) -> Optional[int]:
    """
    Valide et convertit un chat_id
    
    Returns:
        int si valide, None sinon
    """
    try:
        chat_id = int(chat_id_str.strip())
        # Les IDs de groupe/canal sont négatifs
        # Les IDs de supergroupe commencent par -100
        if chat_id < 0 or (chat_id > 0 and len(str(chat_id)) >= 9):
            return chat_id
        return None
    except (ValueError, AttributeError):
        return None