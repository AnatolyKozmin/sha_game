from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.models import Command, User, UserTask, CommandTask


def get_commands_keyboard(commands: list[Command]) -> InlineKeyboardMarkup:
    """Клавиатура со списком команд."""
    builder = InlineKeyboardBuilder()
    
    for cmd in commands:
        name = cmd.name or f"Команда {cmd.number}"
        builder.button(
            text=f"👥 {name}",
            callback_data=f"cmd:{cmd.id}"
        )
    
    builder.adjust(2)  # 2 кнопки в ряд
    return builder.as_markup()


def get_team_members_keyboard(command: Command, users: list[User]) -> InlineKeyboardMarkup:
    """Клавиатура со списком участников команды + кнопка Командная."""
    builder = InlineKeyboardBuilder()
    
    # Кнопка для командных заданий
    builder.button(
        text="📋 Командные задания",
        callback_data=f"team:{command.id}"
    )
    
    # Участники команды
    for user in users:
        # Считаем выполненные задания
        completed = sum(1 for t in user.tasks if t.is_completed)
        total = len(user.tasks)
        builder.button(
            text=f"👤 {user.full_name} ({completed}/{total})",
            callback_data=f"user:{user.id}"
        )
    
    # Кнопка назад
    builder.button(
        text="⬅️ Назад к командам",
        callback_data="back:commands"
    )
    
    builder.adjust(1)  # 1 кнопка в ряд
    return builder.as_markup()


def get_user_tasks_keyboard(user: User, tasks: list[UserTask], command_id: int) -> InlineKeyboardMarkup:
    """Клавиатура с заданиями участника."""
    builder = InlineKeyboardBuilder()
    
    for task in sorted(tasks, key=lambda t: t.task_number):
        status = "✅" if task.is_completed else "❌"
        builder.button(
            text=f"{status} Задание {task.task_number}",
            callback_data=f"utask:{task.id}"
        )
    
    builder.adjust(2)  # 2 кнопки в ряд
    
    # Кнопка назад
    builder.row(
        InlineKeyboardButton(
            text="⬅️ Назад к участникам",
            callback_data=f"cmd:{command_id}"
        )
    )
    
    return builder.as_markup()


def get_command_tasks_keyboard(command: Command, tasks: list[CommandTask]) -> InlineKeyboardMarkup:
    """Клавиатура с командными заданиями."""
    builder = InlineKeyboardBuilder()
    
    for task in sorted(tasks, key=lambda t: t.task_number):
        status = "✅" if task.is_completed else "❌"
        builder.button(
            text=f"{status} Задание {task.task_number}",
            callback_data=f"ctask:{task.id}"
        )
    
    builder.adjust(2)  # 2 кнопки в ряд
    
    # Кнопка назад
    builder.row(
        InlineKeyboardButton(
            text="⬅️ Назад к участникам",
            callback_data=f"cmd:{command.id}"
        )
    )
    
    return builder.as_markup()

