import os
from contextlib import contextmanager
from sqlalchemy import create_engine, Column, Integer, BigInteger, Text, DateTime, Boolean, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

# --- Vérification critique ---
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "❌ La variable d'environnement DATABASE_URL est manquante.\n"
        "➡️ Dans Railway, assure-toi d'avoir ajouté une base PostgreSQL à ton service."
    )

# Configuration optimisée pour production
engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,  # Vérification des connexions
    pool_size=10,  # Connexions dans le pool
    max_overflow=20,  # Connexions supplémentaires
    pool_recycle=3600,  # Recycler les connexions après 1h
    poolclass=QueuePool
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class UserPreferences(Base):
    """Préférences utilisateur avec tous les paramètres"""
    __tablename__ = "user_preferences"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, unique=True, index=True, nullable=False)
    
    # Transformations de texte
    prefix = Column(Text, default="")
    suffix = Column(Text, default="")
    
    # Système de remplacement de mots-clés
    keyword_find = Column(Text, default="")
    keyword_replace = Column(Text, default="")
    
    # Mode publication
    publish_mode = Column(Boolean, default=False)
    target_chat_id = Column(BigInteger, nullable=True)
    
    # État du bot
    conversation_state = Column(Text, default="")  # Pour gérer les états
    buffer_mode = Column(Boolean, default=False)  # Mode buffer activé
    
    # Statistiques
    messages_processed = Column(Integer, default=0)
    messages_failed = Column(Integer, default=0)
    last_activity = Column(DateTime(timezone=True), server_default=func.now())
    
    # Métadonnées
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class MessageBuffer(Base):
    """Buffer temporaire pour le traitement en lot"""
    __tablename__ = "message_buffer"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, index=True, nullable=False)
    message_text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class BotSettings(Base):
    """Paramètres globaux du bot"""
    __tablename__ = "bot_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(Text, unique=True, nullable=False, index=True)
    value = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


# Créer les tables
Base.metadata.create_all(bind=engine)


# --- Context Manager pour la DB ---
@contextmanager
def get_db():
    """Context manager sécurisé pour les sessions DB"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


def get_or_create_user(user_id: int) -> UserPreferences:
    """Récupère ou crée un utilisateur"""
    with get_db() as db:
        prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
        if not prefs:
            prefs = UserPreferences(user_id=user_id)
            db.add(prefs)
            db.flush()  # Pour obtenir l'ID
            db.refresh(prefs)
        return prefs


def update_user_activity(user_id: int):
    """Met à jour la dernière activité"""
    with get_db() as db:
        prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
        if prefs:
            prefs.last_activity = func.now()


def clear_buffer(user_id: int):
    """Vide le buffer d'un utilisateur"""
    with get_db() as db:
        db.query(MessageBuffer).filter(MessageBuffer.user_id == user_id).delete()


def get_buffer_messages(user_id: int) -> list:
    """Récupère les messages du buffer"""
    with get_db() as db:
        messages = db.query(MessageBuffer).filter(
            MessageBuffer.user_id == user_id
        ).order_by(MessageBuffer.created_at).all()
        return [msg.message_text for msg in messages]


def add_to_buffer(user_id: int, text: str):
    """Ajoute un message au buffer"""
    with get_db() as db:
        buffer_msg = MessageBuffer(user_id=user_id, message_text=text)
        db.add(buffer_msg)