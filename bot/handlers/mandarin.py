import logging
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Command as CommandModel, User, UserTask, CommandTask

MAX_PERSONAL_SCORE = 10  # Максимум личных баллов
MAX_TEAM_SCORE = 21      # Максимум командных баллов (7 заданий × 3)
from bot.filters import CheckerFilter
from bot.keyboards import (
    get_commands_keyboard,
    get_team_members_keyboard,
    get_user_tasks_keyboard,
    get_command_tasks_keyboard,
    get_masha_commands_keyboard,
    get_masha_team_details_keyboard,
)

logger = logging.getLogger(__name__)


def sync_to_google_sheets(func):
    """Декоратор для синхронизации с Google Sheets (опционально)."""
    async def wrapper(*args, **kwargs):
        result = await func(*args, **kwargs)
        return result
    return wrapper

router = Router(name="mandarin")

# Фильтр убран - доступ для всех


@router.message(Command("mandarin"))
async def cmd_mandarin(message: Message, session: AsyncSession):
    """Команда /mandarin - показать список команд."""
    result = await session.execute(
        select(CommandModel).order_by(CommandModel.number)
    )
    commands = result.scalars().all()
    
    if not commands:
        await message.answer("📭 Команды ещё не добавлены.")
        return
    
    await message.answer(
        "🍊 <b>Выбери команду:</b>",
        reply_markup=get_commands_keyboard(commands),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "back:commands")
async def callback_back_to_commands(callback: CallbackQuery, session: AsyncSession):
    """Возврат к списку команд."""
    result = await session.execute(
        select(CommandModel).order_by(CommandModel.number)
    )
    commands = result.scalars().all()
    
    await callback.message.edit_text(
        "🍊 <b>Выбери команду:</b>",
        reply_markup=get_commands_keyboard(commands),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cmd:"))
async def callback_select_command(callback: CallbackQuery, session: AsyncSession):
    """Выбор команды - показать участников."""
    command_id = int(callback.data.split(":")[1])
    
    # Загружаем команду с участниками, их заданиями И командными заданиями
    result = await session.execute(
        select(CommandModel)
        .options(
            selectinload(CommandModel.users).selectinload(User.tasks),
            selectinload(CommandModel.tasks)  # Добавили загрузку командных заданий
        )
        .where(CommandModel.id == command_id)
    )
    command = result.scalar_one_or_none()
    
    if not command:
        await callback.answer("❌ Команда не найдена", show_alert=True)
        return
    
    # Считаем статистику (теперь tasks загружены)
    total_users = len(command.users)
    users_score = sum(u.score for u in command.users)
    total_score = command.score + users_score
    
    name = command.name or f"Команда {command.number}"
    text = (
        f"👥 <b>{name}</b>\n\n"
        f"📊 Участников: {total_users}\n"
        f"⭐ Баллы команды: {total_score}\n\n"
        f"Выбери участника или командные задания:"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_team_members_keyboard(command, command.users),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("user:"))
async def callback_select_user(callback: CallbackQuery, session: AsyncSession):
    """Выбор участника - показать его задания."""
    user_id = int(callback.data.split(":")[1])
    
    result = await session.execute(
        select(User)
        .options(selectinload(User.tasks))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        await callback.answer("❌ Участник не найден", show_alert=True)
        return
    
    completed = sum(1 for t in user.tasks if t.is_completed)
    total = len(user.tasks)
    
    # Формируем текст с описанием заданий
    tasks_text = ""
    for task in sorted(user.tasks, key=lambda t: t.task_number):
        status = "✅" if task.is_completed else "❌"
        tasks_text += f"\n{status} <b>Задание {task.task_number}:</b> {task.description}"
    
    text = (
        f"👤 <b>{user.full_name}</b>\n\n"
        f"⭐ Баллы: {user.score}\n"
        f"📋 Выполнено: {completed}/{total}\n"
        f"\n<b>Задания:</b>{tasks_text}"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_user_tasks_keyboard(user, user.tasks, user.command_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("team:"))
async def callback_team_tasks(callback: CallbackQuery, session: AsyncSession):
    """Командные задания."""
    command_id = int(callback.data.split(":")[1])
    
    result = await session.execute(
        select(CommandModel)
        .options(selectinload(CommandModel.tasks))
        .where(CommandModel.id == command_id)
    )
    command = result.scalar_one_or_none()
    
    if not command:
        await callback.answer("❌ Команда не найдена", show_alert=True)
        return
    
    completed = sum(1 for t in command.tasks if t.is_completed)
    total = len(command.tasks)
    
    # Формируем текст с описанием заданий
    tasks_text = ""
    for task in sorted(command.tasks, key=lambda t: t.task_number):
        status = "✅" if task.is_completed else "❌"
        tasks_text += f"\n{status} <b>Задание {task.task_number}:</b> {task.description}"
    
    name = command.name or f"Команда {command.number}"
    text = (
        f"📋 <b>Командные задания - {name}</b>\n\n"
        f"⭐ Баллы за задания: {completed * 3}\n"
        f"✅ Выполнено: {completed}/{total}\n"
        f"\n<b>Задания:</b>{tasks_text}"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_command_tasks_keyboard(command, command.tasks),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("utask:"))
async def callback_toggle_user_task(callback: CallbackQuery, session: AsyncSession):
    """Переключить статус задания участника."""
    task_id = int(callback.data.split(":")[1])
    
    # Загружаем задание с пользователем, его заданиями И командой
    result = await session.execute(
        select(UserTask)
        .options(
            selectinload(UserTask.user).selectinload(User.tasks),
            selectinload(UserTask.user).selectinload(User.command)
        )
        .where(UserTask.id == task_id)
    )
    task = result.scalar_one_or_none()
    
    if not task:
        await callback.answer("❌ Задание не найдено", show_alert=True)
        return
    
    user = task.user
    command = user.command
    
    # Переключаем статус
    task.is_completed = not task.is_completed
    
    # Обновляем баллы (только личные, командные не трогаем)
    if task.is_completed:
        user.score += 1
        await callback.answer("✅ Задание выполнено! +1 балл участнику")
        
        # Записываем время достижения 10 личных баллов
        if user.score == MAX_PERSONAL_SCORE and user.max_reached_at is None:
            user.max_reached_at = datetime.utcnow()
            logger.info(f"User {user.id} reached max personal score at {user.max_reached_at}")
    else:
        user.score -= 1
        # Сбрасываем время если упали ниже максимума
        if user.score < MAX_PERSONAL_SCORE:
            user.max_reached_at = None
        await callback.answer("❌ Задание отменено. -1 балл участнику")
    
    await session.commit()
    
    # Синхронизация с Google Sheets
    try:
        from config import get_settings
        from scripts.sheets_updater import update_user_task_status
        settings = get_settings()
        if settings.google_sheet_id:
            update_user_task_status(
                spreadsheet_id=settings.google_sheet_id,
                command_number=command.number,
                user_index=user.sheet_index,
                task_number=task.task_number,
                is_completed=task.is_completed
            )
            logger.info(f"Google Sheets updated: user task {task.id} = {task.is_completed}")
    except Exception as e:
        logger.warning(f"Failed to sync with Google Sheets: {e}")
    
    completed = sum(1 for t in user.tasks if t.is_completed)
    total = len(user.tasks)
    
    tasks_text = ""
    for t in sorted(user.tasks, key=lambda x: x.task_number):
        status = "✅" if t.is_completed else "❌"
        tasks_text += f"\n{status} <b>Задание {t.task_number}:</b> {t.description}"
    
    text = (
        f"👤 <b>{user.full_name}</b>\n\n"
        f"⭐ Баллы: {user.score}\n"
        f"📋 Выполнено: {completed}/{total}\n"
        f"\n<b>Задания:</b>{tasks_text}"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_user_tasks_keyboard(user, user.tasks, user.command_id),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("ctask:"))
async def callback_toggle_command_task(callback: CallbackQuery, session: AsyncSession):
    """Переключить статус командного задания."""
    task_id = int(callback.data.split(":")[1])
    
    result = await session.execute(
        select(CommandTask)
        .options(
            selectinload(CommandTask.command).selectinload(CommandModel.tasks),
            selectinload(CommandTask.command).selectinload(CommandModel.users)
        )
        .where(CommandTask.id == task_id)
    )
    task = result.scalar_one_or_none()
    
    if not task:
        await callback.answer("❌ Задание не найдено", show_alert=True)
        return
    
    command = task.command
    
    # Переключаем статус
    task.is_completed = not task.is_completed
    
    # Обновляем баллы команды
    if task.is_completed:
        command.score += 3
        await callback.answer("✅ Командное задание выполнено! +3 балла команде")
    else:
        command.score -= 3
        await callback.answer("❌ Командное задание отменено. -3 балла команде")
    
    await session.commit()
    
    # Синхронизация с Google Sheets
    try:
        from config import get_settings
        from scripts.sheets_updater import update_command_task_status
        settings = get_settings()
        if settings.google_sheet_id:
            update_command_task_status(
                spreadsheet_id=settings.google_sheet_id,
                command_number=command.number,
                task_number=task.task_number,
                is_completed=task.is_completed
            )
            logger.info(f"Google Sheets updated: command task {task.id} = {task.is_completed}")
    except Exception as e:
        logger.warning(f"Failed to sync with Google Sheets: {e}")
    
    completed = sum(1 for t in command.tasks if t.is_completed)
    total = len(command.tasks)
    
    tasks_text = ""
    for t in sorted(command.tasks, key=lambda x: x.task_number):
        status = "✅" if t.is_completed else "❌"
        tasks_text += f"\n{status} <b>Задание {t.task_number}:</b> {t.description}"
    
    name = command.name or f"Команда {command.number}"
    text = (
        f"📋 <b>Командные задания - {name}</b>\n\n"
        f"⭐ Баллы за задания: {completed * 3}\n"
        f"✅ Выполнено: {completed}/{total}\n"
        f"\n<b>Задания:</b>{tasks_text}"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_command_tasks_keyboard(command, command.tasks),
        parse_mode="HTML"
    )


# ===== Команда /masha - просмотр баллов команд и участников =====

@router.message(Command("masha"))
async def cmd_masha(message: Message, session: AsyncSession):
    """Команда /masha - показать рейтинг команд с общими баллами."""
    result = await session.execute(
        select(CommandModel)
        .options(selectinload(CommandModel.users))
        .order_by(CommandModel.number)
    )
    commands = result.scalars().all()
    
    if not commands:
        await message.answer("📭 Команды ещё не добавлены.")
        return
    
    # Считаем общие баллы для текста
    total_all = sum(cmd.total_score for cmd in commands)
    
    await message.answer(
        f"🏆 <b>Рейтинг команд</b>\n\n"
        f"📊 Всего баллов: {total_all}\n\n"
        f"Выбери команду для просмотра участников:",
        reply_markup=get_masha_commands_keyboard(commands),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "masha_back:commands")
async def callback_masha_back_to_commands(callback: CallbackQuery, session: AsyncSession):
    """Возврат к списку команд в /masha."""
    result = await session.execute(
        select(CommandModel)
        .options(selectinload(CommandModel.users))
        .order_by(CommandModel.number)
    )
    commands = result.scalars().all()
    
    total_all = sum(cmd.total_score for cmd in commands)
    
    await callback.message.edit_text(
        f"🏆 <b>Рейтинг команд</b>\n\n"
        f"📊 Всего баллов: {total_all}\n\n"
        f"Выбери команду для просмотра участников:",
        reply_markup=get_masha_commands_keyboard(commands),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("masha_cmd:"))
async def callback_masha_select_command(callback: CallbackQuery, session: AsyncSession):
    """Выбор команды в /masha - показать участников с баллами."""
    command_id = int(callback.data.split(":")[1])
    
    result = await session.execute(
        select(CommandModel)
        .options(selectinload(CommandModel.users))
        .where(CommandModel.id == command_id)
    )
    command = result.scalar_one_or_none()
    
    if not command:
        await callback.answer("❌ Команда не найдена", show_alert=True)
        return
    
    name = command.name or f"Команда {command.number}"
    users_score = sum(u.score for u in command.users)
    
    # Формируем текст с участниками
    sorted_users = sorted(command.users, key=lambda u: u.score, reverse=True)
    users_text = ""
    for i, user in enumerate(sorted_users):
        medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"{i+1}."
        users_text += f"\n{medal} {user.full_name}: <b>{user.score}</b> баллов"
    
    text = (
        f"👥 <b>{name}</b>\n\n"
        f"⭐ Командные баллы: {command.score}\n"
        f"👤 Баллы участников: {users_score}\n"
        f"📊 <b>Всего: {command.total_score}</b>\n\n"
        f"<b>Участники:</b>{users_text}"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_masha_team_details_keyboard(command, command.users),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("masha_user_info:"))
async def callback_masha_user_info(callback: CallbackQuery, session: AsyncSession):
    """Показать информацию об участнике (alert)."""
    user_id = int(callback.data.split(":")[1])
    
    result = await session.execute(
        select(User)
        .options(selectinload(User.tasks), selectinload(User.command))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        await callback.answer("❌ Участник не найден", show_alert=True)
        return
    
    completed = sum(1 for t in user.tasks if t.is_completed)
    total = len(user.tasks)
    
    await callback.answer(
        f"👤 {user.full_name}\n"
        f"⭐ Баллы: {user.score}\n"
        f"📋 Заданий: {completed}/{total}",
        show_alert=True
    )
