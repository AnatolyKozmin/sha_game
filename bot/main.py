import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import get_settings
from database.engine import engine, async_session, init_db
from bot.handlers import mandarin_router, parsing_router
from bot.middlewares import DatabaseMiddleware


# Логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot):
    """Действия при запуске бота."""
    me = await bot.get_me()
    logger.info(f"Бот запущен: @{me.username}")


async def on_shutdown(bot: Bot):
    """Действия при остановке бота."""
    logger.info("Бот останавливается...")


async def main():
    """Точка входа."""
    settings = get_settings()
    
    # Миграции применяются через Alembic перед запуском (см. Dockerfile)
    logger.info("Подключение к базе данных...")
    
    # Инициализация бота
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()
    
    # Регистрация обработчиков startup/shutdown
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    # Регистрация middleware
    dp.message.middleware(DatabaseMiddleware(async_session))
    dp.callback_query.middleware(DatabaseMiddleware(async_session))
    
    # Регистрация роутеров
    dp.include_router(mandarin_router)
    dp.include_router(parsing_router)
    
    # Запуск polling
    logger.info("Запуск бота...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await engine.dispose()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")

