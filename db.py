# db.py
import os
from sqlalchemy import create_engine, Column, Integer, BigInteger, Text, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# --- Vérification critique ---
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "❌ La variable d'environnement DATABASE_URL est manquante.\n"
        "➡️ Dans Railway, assure-toi d'avoir ajouté une base PostgreSQL à ton service."
    )

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class UserPreferences(Base):
    __tablename__ = "user_preferences"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, unique=True, index=True, nullable=False)
    prefix = Column(Text, default="")
    suffix = Column(Text, default="")
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

# Crée les tables si elles n'existent pas
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()