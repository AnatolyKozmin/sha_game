"""
Обработчик команды /sosi_parsing для парсинга Google Sheets.
"""

from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from bot.filters import CheckerFilter
from config import get_settings
from scripts.parser import parse_all
from scripts.import_to_db import import_commands_to_db

router = Router(name="parsing")

# Оставляем фильтр для парсинга - только проверяющие
router.message.filter(CheckerFilter())


@router.message(Command("sosi_parsing"))
async def cmd_sosi_parsing(message: Message, session: AsyncSession):
    """Запуск парсинга Google Sheets и импорта в БД."""
    settings = get_settings()
    
    if not settings.google_sheet_id:
        await message.answer("❌ GOOGLE_SHEET_ID не указан в .env")
        return
    
    status_msg = await message.answer("🔄 Начинаю парсинг Google Sheets...")
    
    try:
        # Парсим данные
        await status_msg.edit_text("📊 Парсинг таблицы... (это может занять ~15 сек)")
        parsed_data = parse_all(settings.google_sheet_id)
        
        # Импортируем в БД
        await status_msg.edit_text("💾 Импорт данных в базу...")
        stats = await import_commands_to_db(session, parsed_data)
        
        # Формируем отчёт
        report = (
            "✅ <b>Парсинг завершён!</b>\n\n"
            f"📋 Команд создано: {stats['commands_created']}\n"
            f"📋 Команд обновлено: {stats['commands_updated']}\n"
            f"👥 Участников создано: {stats['users_created']}\n"
            f"👥 Участников обновлено: {stats['users_updated']}\n"
            f"📝 Командных заданий: {stats['command_tasks_created']}\n"
            f"📝 Индивидуальных заданий: {stats['user_tasks_created']}"
        )
        
        await status_msg.edit_text(report, parse_mode="HTML")
        
    except FileNotFoundError as e:
        await status_msg.edit_text(f"❌ {e}")
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка парсинга: {e}")
        raise

