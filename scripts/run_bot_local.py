"""
Запуск бота локально с SQLite базой (для тестирования).

Запуск:
    python -m scripts.run_bot_local
"""

import asyncio
import logging
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from database.models import Base
from bot.handlers import mandarin_router, parsing_router
from bot.middlewares import DatabaseMiddleware


PROJECT_ROOT = Path(__file__).parent.parent
SQLITE_PATH = PROJECT_ROOT / "test_local.db"

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def main():
    # Проверяем наличие БД
    if not SQLITE_PATH.exists():
        print("❌ База данных не найдена!")
        print("   Сначала выполни: python -m scripts.local_test")
        return
    
    # Загружаем токен бота
    try:
        from config import get_settings
        bot_token = get_settings().bot_token
    except Exception:
        bot_token = input("Введи BOT_TOKEN: ").strip()
        if not bot_token:
            print("❌ Токен не указан")
            return
    
    # SQLite с aiosqlite
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{SQLITE_PATH}",
        echo=False,
    )
    
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    # Бот
    bot = Bot(
        token=bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()
    
    # Middleware
    dp.message.middleware(DatabaseMiddleware(async_session))
    dp.callback_query.middleware(DatabaseMiddleware(async_session))
    
    # Роутеры
    dp.include_router(mandarin_router)
    dp.include_router(parsing_router)
    
    # Запуск
    me = await bot.get_me()
    logger.info(f"🤖 Бот запущен: @{me.username}")
    logger.info(f"📂 База данных: {SQLITE_PATH}")
    logger.info("⏳ Ожидание команд...")
    
    try:
        await dp.start_polling(bot)
    finally:
        await engine.dispose()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")

