import asyncio
import logging
from typing import List, Dict
from telegram import Message
from telegram.ext import ContextTypes
from telegram.error import TelegramError, RetryAfter

from db import get_db, UserPreferences

logger = logging.getLogger(__name__)


class MessageProcessor:
    """Gestionnaire optimisé pour le traitement massif de messages"""
    
    def __init__(self, max_concurrent: int = 10, rate_limit_delay: float = 0.05):
        self.max_concurrent = max_concurrent
        self.rate_limit_delay = rate_limit_delay
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.processed_count = 0
        self.failed_count = 0
    
    async def process_single_message(
        self, 
        message_text: str, 
        prefs: UserPreferences,
        context: ContextTypes.DEFAULT_TYPE,
        target_chat_id: int = None,
        retry_count: int = 3
    ) -> Dict:
        """
        Traite un message unique avec gestion des erreurs et retry
        
        Returns:
            Dict avec status, processed_text, et error si applicable
        """
        async with self.semaphore:
            try:
                # Appliquer les transformations
                processed_text = message_text
                
                # Remplacement de mots-clés
                if prefs.keyword_find and prefs.keyword_replace:
                    processed_text = processed_text.replace(
                        prefs.keyword_find, 
                        prefs.keyword_replace
                    )
                
                # Ajout préfixe/suffixe
                processed_text = f"{prefs.prefix}{processed_text}{prefs.suffix}"
                
                # Envoi du message
                chat_id = target_chat_id or prefs.target_chat_id
                
                if chat_id:
                    attempt = 0
                    while attempt < retry_count:
                        try:
                            await context.bot.send_message(
                                chat_id=chat_id,
                                text=processed_text
                            )
                            
                            # Délai anti-rate-limit
                            await asyncio.sleep(self.rate_limit_delay)
                            
                            self.processed_count += 1
                            return {
                                "status": "success",
                                "processed_text": processed_text,
                                "original_text": message_text
                            }
                        
                        except RetryAfter as e:
                            # Telegram demande d'attendre
                            wait_time = e.retry_after + 1
                            logger.warning(f"Rate limit atteint, attente de {wait_time}s")
                            await asyncio.sleep(wait_time)
                            attempt += 1
                        
                        except TelegramError as e:
                            if "chat not found" in str(e).lower():
                                raise  # Ne pas retry si le chat n'existe pas
                            attempt += 1
                            await asyncio.sleep(1)
                    
                    # Si tous les retries échouent
                    raise Exception(f"Échec après {retry_count} tentatives")
                
                else:
                    # Pas de chat cible défini
                    return {
                        "status": "no_target",
                        "processed_text": processed_text,
                        "original_text": message_text
                    }
            
            except Exception as e:
                self.failed_count += 1
                logger.error(f"Erreur traitement message: {e}")
                return {
                    "status": "error",
                    "error": str(e),
                    "original_text": message_text
                }
    
    async def process_batch(
        self,
        messages: List[str],
        user_id: int,
        context: ContextTypes.DEFAULT_TYPE,
        progress_callback = None
    ) -> Dict:
        """
        Traite un lot de messages en parallèle
        
        Args:
            messages: Liste des textes à traiter
            user_id: ID de l'utilisateur
            context: Contexte Telegram
            progress_callback: Fonction appelée pour chaque message traité
        
        Returns:
            Dict avec statistiques et résultats
        """
        # Récupérer les préférences
        db = next(get_db())
        prefs = db.query(UserPreferences).filter(
            UserPreferences.user_id == user_id
        ).first()
        
        if not prefs:
            db.close()
            return {
                "status": "error",
                "error": "Préférences utilisateur introuvables"
            }
        
        # Réinitialiser les compteurs
        self.processed_count = 0
        self.failed_count = 0
        
        # Créer les tâches
        tasks = []
        for idx, msg in enumerate(messages):
            task = self.process_single_message(
                message_text=msg,
                prefs=prefs,
                context=context
            )
            tasks.append(task)
        
        # Exécuter en parallèle avec progression
        results = []
        for idx, task in enumerate(asyncio.as_completed(tasks)):
            result = await task
            results.append(result)
            
            if progress_callback:
                await progress_callback(idx + 1, len(messages), result)
        
        db.close()
        
        return {
            "total": len(messages),
            "successful": self.processed_count,
            "failed": self.failed_count,
            "results": results
        }
    
    async def process_forwarded_messages(
        self,
        user_id: int,
        forwarded_messages: List[Message],
        context: ContextTypes.DEFAULT_TYPE,
        progress_callback = None
    ) -> Dict:
        """
        Traite des messages forwardés en extrayant leur texte
        """
        # Extraire le texte de chaque message
        message_texts = []
        for msg in forwarded_messages:
            if msg.text:
                message_texts.append(msg.text)
            elif msg.caption:
                message_texts.append(msg.caption)
        
        if not message_texts:
            return {
                "status": "error",
                "error": "Aucun texte trouvé dans les messages"
            }
        
        return await self.process_batch(
            messages=message_texts,
            user_id=user_id,
            context=context,
            progress_callback=progress_callback
        )


# Instance globale pour réutilisation
message_processor = MessageProcessor(max_concurrent=20, rate_limit_delay=0.03)


async def handle_bulk_processing(
    user_id: int,
    messages: List[str],
    context: ContextTypes.DEFAULT_TYPE,
    status_message = None
):
    """
    Fonction helper pour le traitement bulk avec mise à jour du statut
    """
    async def update_progress(current: int, total: int, result: Dict):
        if status_message and current % 5 == 0:  # Mise à jour tous les 5 messages
            try:
                progress_bar = "▓" * (current * 20 // total) + "░" * (20 - (current * 20 // total))
                await status_message.edit_text(
                    f"⚙️ <b>Traitement en cours...</b>\n\n"
                    f"[{progress_bar}] {current}/{total}\n"
                    f"✅ Réussis: {message_processor.processed_count}\n"
                    f"❌ Échecs: {message_processor.failed_count}",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Erreur mise à jour progression: {e}")
    
    result = await message_processor.process_batch(
        messages=messages,
        user_id=user_id,
        context=context,
        progress_callback=update_progress
    )
    
    return result