"""
Импорт данных из парсера в базу данных.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Command, User, UserTask, CommandTask
from scripts.parser import CommandData, UserData, TaskData


async def import_commands_to_db(
    session: AsyncSession,
    parsed_data: list[CommandData]
) -> dict:
    """
    Импорт спарсенных данных в БД.
    
    Returns:
        Статистика импорта
    """
    stats = {
        "commands_created": 0,
        "commands_updated": 0,
        "users_created": 0,
        "users_updated": 0,
        "command_tasks_created": 0,
        "user_tasks_created": 0,
    }
    
    for cmd_data in parsed_data:
        # Ищем или создаём команду
        result = await session.execute(
            select(Command).where(Command.number == cmd_data.number)
        )
        command = result.scalar_one_or_none()
        
        if command is None:
            command = Command(
                number=cmd_data.number,
                name=cmd_data.name,
                score=0,
            )
            session.add(command)
            await session.flush()  # Получаем ID
            stats["commands_created"] += 1
        else:
            command.name = cmd_data.name
            stats["commands_updated"] += 1
        
        # Командные задания
        for task_data in cmd_data.tasks:
            # Проверяем, есть ли уже такое задание
            result = await session.execute(
                select(CommandTask).where(
                    CommandTask.command_id == command.id,
                    CommandTask.task_number == task_data.number
                )
            )
            task = result.scalar_one_or_none()
            
            if task is None:
                task = CommandTask(
                    command_id=command.id,
                    task_number=task_data.number,
                    description=task_data.description,
                    is_completed=task_data.is_completed,
                )
                session.add(task)
                stats["command_tasks_created"] += 1
            else:
                task.description = task_data.description
                task.is_completed = task_data.is_completed
        
        # Участники команды
        for user_data in cmd_data.users:
            # Ищем участника по имени и команде
            result = await session.execute(
                select(User).where(
                    User.command_id == command.id,
                    User.first_name == user_data.first_name,
                    User.last_name == user_data.last_name
                )
            )
            user = result.scalar_one_or_none()
            
            if user is None:
                user = User(
                    first_name=user_data.first_name,
                    last_name=user_data.last_name,
                    command_id=command.id,
                    sheet_index=user_data.sheet_index,
                    score=0,
                )
                session.add(user)
                await session.flush()  # Получаем ID
                stats["users_created"] += 1
            else:
                user.sheet_index = user_data.sheet_index
                stats["users_updated"] += 1
            
            # Индивидуальные задания участника
            for task_data in user_data.tasks:
                result = await session.execute(
                    select(UserTask).where(
                        UserTask.user_id == user.id,
                        UserTask.task_number == task_data.number
                    )
                )
                task = result.scalar_one_or_none()
                
                if task is None:
                    task = UserTask(
                        user_id=user.id,
                        task_number=task_data.number,
                        description=task_data.description,
                        is_completed=task_data.is_completed,
                    )
                    session.add(task)
                    stats["user_tasks_created"] += 1
                else:
                    task.description = task_data.description
                    task.is_completed = task_data.is_completed
    
    await session.commit()
    return stats

