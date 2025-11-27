"""
Локальный тест: импорт JSON в SQLite и проверка данных.

Запуск:
    python -m scripts.local_test
"""

import json
import asyncio
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from database.models import Base, Command, User, UserTask, CommandTask


PROJECT_ROOT = Path(__file__).parent.parent
JSON_PATH = PROJECT_ROOT / "parsed_data.json"
SQLITE_PATH = PROJECT_ROOT / "test_local.db"


def load_json_data() -> list[dict]:
    """Загрузить данные из JSON."""
    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def import_to_sqlite(data: list[dict]):
    """Импортировать данные в SQLite."""
    # Удаляем старую БД если есть
    if SQLITE_PATH.exists():
        SQLITE_PATH.unlink()
    
    # Создаём синхронный движок для SQLite
    engine = create_engine(f"sqlite:///{SQLITE_PATH}", echo=False)
    
    # Создаём таблицы
    Base.metadata.create_all(engine)
    
    with Session(engine) as session:
        for cmd_data in data:
            # Создаём команду
            command = Command(
                number=cmd_data["number"],
                name=cmd_data["name"],
                score=0,
            )
            session.add(command)
            session.flush()
            
            # Командные задания
            for task_data in cmd_data["tasks"]:
                task = CommandTask(
                    command_id=command.id,
                    task_number=task_data["number"],
                    description=task_data["description"],
                    is_completed=task_data["is_completed"],
                )
                session.add(task)
            
            # Участники
            for idx, user_data in enumerate(cmd_data["users"]):
                user = User(
                    first_name=user_data["first_name"],
                    last_name=user_data["last_name"],
                    command_id=command.id,
                    sheet_index=user_data.get("sheet_index", idx),
                    score=0,
                )
                session.add(user)
                session.flush()
                
                # Индивидуальные задания
                for task_data in user_data["tasks"]:
                    task = UserTask(
                        user_id=user.id,
                        task_number=task_data["number"],
                        description=task_data["description"],
                        is_completed=task_data["is_completed"],
                    )
                    session.add(task)
        
        session.commit()
    
    return engine


def print_stats(engine):
    """Вывести статистику по данным."""
    with Session(engine) as session:
        commands = session.execute(select(Command)).scalars().all()
        users = session.execute(select(User)).scalars().all()
        cmd_tasks = session.execute(select(CommandTask)).scalars().all()
        user_tasks = session.execute(select(UserTask)).scalars().all()
        
        print("\n" + "="*60)
        print("📊 СТАТИСТИКА ИМПОРТА:")
        print("="*60)
        print(f"  📋 Команд: {len(commands)}")
        print(f"  👥 Участников: {len(users)}")
        print(f"  📝 Командных заданий: {len(cmd_tasks)}")
        print(f"  📝 Индивидуальных заданий: {len(user_tasks)}")
        
        print("\n" + "-"*60)
        print("👥 КОМАНДЫ И УЧАСТНИКИ:")
        print("-"*60)
        
        for cmd in sorted(commands, key=lambda c: c.number):
            cmd_users = [u for u in users if u.command_id == cmd.id]
            print(f"\n  🏷️  Команда {cmd.number} ({cmd.name}):")
            print(f"      Участников: {len(cmd_users)}")
            for user in cmd_users[:3]:  # Показываем первых 3
                print(f"        • {user.last_name} {user.first_name}")
            if len(cmd_users) > 3:
                print(f"        ... и ещё {len(cmd_users) - 3}")


def main():
    print("🔄 Загрузка данных из JSON...")
    data = load_json_data()
    print(f"✅ Загружено {len(data)} команд")
    
    print("\n💾 Импорт в SQLite...")
    engine = import_to_sqlite(data)
    print(f"✅ База создана: {SQLITE_PATH}")
    
    print_stats(engine)
    
    print("\n" + "="*60)
    print("🚀 Теперь можно запустить бота с SQLite!")
    print("   Выполни: python -m scripts.run_bot_local")
    print("="*60)


if __name__ == "__main__":
    main()

