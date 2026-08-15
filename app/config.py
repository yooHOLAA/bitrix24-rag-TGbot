"""Централизованная конфигурация проекта (pydantic-settings).

Все настройки собраны в одном классе Settings и загружаются из .env.
Обязательные поля (без дефолтов) валидируются при старте: если в .env
чего-то не хватает, вы получите понятную ValidationError со списком
отсутствующих переменных.
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Путь к .env относительно ЭТОГО файла (не зависит от cwd запуска)
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # === PostgreSQL ===
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "bitrix_rag_db"
    DB_USER: str = "bitrix_user"
    DB_PASSWORD: str  # обязательное, без дефолта

    # === Telegram Bot ===
    TELEGRAM_BOT_TOKEN: str  # обязательное

    # === Yandex Cloud ===
    YANDEX_FOLDER_ID: str  # обязательное
    YANDEX_API_KEY: str  # обязательное

    @property
    def database_url(self) -> str:
        """Строка подключения к PostgreSQL."""
        return (
            f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def yandexgpt_model_uri(self) -> str:
        """modelUri для YandexGPT."""
        return f"gpt://{self.YANDEX_FOLDER_ID}/yandexgpt/latest"

    @property
    def embedding_doc_uri(self) -> str:
        """modelUri для эмбеддингов документов (понадобится в векторном поиске)."""
        return f"emb://{self.YANDEX_FOLDER_ID}/text-search-doc/latest"

    @property
    def embedding_query_uri(self) -> str:
        """modelUri для эмбеддингов запросов."""
        return f"emb://{self.YANDEX_FOLDER_ID}/text-search-query/latest"


@lru_cache
def get_settings() -> Settings:
    """Единственный экземпляр настроек (кэшируется)."""
    return Settings()
