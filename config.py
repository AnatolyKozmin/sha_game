from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Настройки приложения из переменных окружения."""
    
    # Telegram Bot
    bot_token: str
    
    # PostgreSQL
    database_url: str
    
    # Google Sheets (опционально, для парсера)
    google_sheet_id: str = ""
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Игнорировать лишние переменные (POSTGRES_USER и т.д.)


@lru_cache
def get_settings() -> Settings:
    """Получить закэшированный экземпляр настроек."""
    return Settings()

