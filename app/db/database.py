"""Модуль базы данных: engine, сессии, создание таблиц."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from ..config import get_settings

settings = get_settings()

# Движок и фабрика сессий (URL берётся из Settings)
engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Единый Base для всех моделей
Base = declarative_base()


def get_db():
    """Единая зависимость для получения сессии БД."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Создаёт все таблицы. Импорт моделей нужен, чтобы Base их 'увидел'."""
    from . import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
