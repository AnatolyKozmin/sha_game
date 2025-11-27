"""
Парсер Google Sheets для команд и участников.

Структура таблицы:
- Лист "команды": 10 команд с 7 заданиями каждая
- Листы "1"-"10": участники команд с 10 индивидуальными заданиями

Запуск тестово (создаёт JSON):
    python -m scripts.parser --test

Запуск для импорта в БД:
    python -m scripts.parser
"""

import json
import time
import argparse
from pathlib import Path
from dataclasses import dataclass, asdict

import gspread
from google.oauth2.service_account import Credentials


# Google API rate limits - делаем паузы между запросами
RATE_LIMIT_DELAY = 1.0  # секунда между запросами к листам

# Пути к файлам
PROJECT_ROOT = Path(__file__).parent.parent
CREDENTIALS_PATH = PROJECT_ROOT / "credentials.json"

# Google Sheets API scopes
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


@dataclass
class TaskData:
    """Данные задания."""
    number: int
    description: str
    is_completed: bool


@dataclass
class UserData:
    """Данные участника."""
    last_name: str
    first_name: str
    command_number: int
    sheet_index: int  # Позиция на листе (0-11)
    tasks: list[TaskData]


@dataclass
class CommandData:
    """Данные команды."""
    number: int
    name: str
    tasks: list[TaskData]
    users: list[UserData]


def get_google_client() -> gspread.Client:
    """Инициализация клиента Google Sheets."""
    if not CREDENTIALS_PATH.exists():
        raise FileNotFoundError(
            f"credentials.json не найден по пути: {CREDENTIALS_PATH}\n"
            "Скачай его из Google Cloud Console."
        )
    
    creds = Credentials.from_service_account_file(
        str(CREDENTIALS_PATH),
        scopes=SCOPES
    )
    return gspread.authorize(creds)


def is_completed(value: str | None) -> bool:
    """Проверить, выполнено ли задание."""
    if not value:
        return False
    return "сделано" in value.lower() or "выполнено" in value.lower()


def parse_name(full_name: str) -> tuple[str, str]:
    """Разбить ФИО на фамилию и имя."""
    parts = full_name.strip().split()
    if len(parts) >= 2:
        return parts[0], parts[1]  # Фамилия, Имя
    elif len(parts) == 1:
        return parts[0], ""
    return "", ""


def parse_commands_sheet(worksheet: gspread.Worksheet) -> dict[int, CommandData]:
    """
    Парсинг листа 'команды'.
    
    Структура:
    - Row 1: A1=1 команда, D1=2 команда, H1=3 команда, L1=4 команда, P1=5 команда
    - Row 9: A9=6 команда, D9=7 команда, H9=8 команда, L9=9 команда, P9=10 команда
    - Под каждой командой 7 заданий
    - Справа от задания (col+1) - статус выполнения
    """
    print("📋 Парсинг листа 'команды'...")
    
    # Получаем все данные одним запросом (экономим rate limit)
    all_values = worksheet.get_all_values()
    
    # Позиции команд: (col, row, command_number)
    command_positions = [
        (0, 0, 1),    # A1 - 1 команда
        (3, 0, 2),    # D1 - 2 команда
        (7, 0, 3),    # H1 - 3 команда
        (11, 0, 4),   # L1 - 4 команда
        (15, 0, 5),   # P1 - 5 команда
        (0, 8, 6),    # A9 - 6 команда
        (3, 8, 7),    # D9 - 7 команда
        (7, 8, 8),    # H9 - 8 команда
        (11, 8, 9),   # L9 - 9 команда
        (15, 8, 10),  # P9 - 10 команда
    ]
    
    commands = {}
    
    for col, row, cmd_num in command_positions:
        # Название команды
        try:
            name = all_values[row][col] if row < len(all_values) and col < len(all_values[row]) else f"{cmd_num} команда"
        except IndexError:
            name = f"{cmd_num} команда"
        
        # 7 заданий под командой
        tasks = []
        for i in range(7):
            task_row = row + 1 + i
            try:
                description = all_values[task_row][col] if task_row < len(all_values) and col < len(all_values[task_row]) else ""
                # Статус справа от задания
                status_col = col + 1
                status = all_values[task_row][status_col] if task_row < len(all_values) and status_col < len(all_values[task_row]) else ""
                completed = is_completed(status)
            except IndexError:
                description = ""
                completed = False
            
            tasks.append(TaskData(
                number=i + 1,
                description=description.strip() if description else f"Командное задание {i + 1}",
                is_completed=completed
            ))
        
        commands[cmd_num] = CommandData(
            number=cmd_num,
            name=name.strip() if name else f"{cmd_num} команда",
            tasks=tasks,
            users=[]
        )
        print(f"  ✅ Команда {cmd_num}: {len(tasks)} заданий")
    
    return commands


def parse_users_sheet(worksheet: gspread.Worksheet, command_number: int) -> list[UserData]:
    """
    Парсинг листа с участниками команды.
    
    Структура (12 участников на лист):
    - Row 1: A1, D1, G1, J1 - фамилии
    - Row 12: A12, D12, G12, J12 - фамилии
    - Row 23: A23, D23, G23, J23 - фамилии
    - Под каждой фамилией 10 заданий
    - Справа от задания (col+1) - статус выполнения
    """
    print(f"👥 Парсинг листа '{command_number}' (участники команды {command_number})...")
    
    # Получаем все данные одним запросом
    all_values = worksheet.get_all_values()
    
    # Позиции участников: (col, row)
    user_positions = [
        # Первый ряд (row 0)
        (0, 0),   # A1
        (3, 0),   # D1
        (6, 0),   # G1
        (9, 0),   # J1
        # Второй ряд (row 11)
        (0, 11),  # A12
        (3, 11),  # D12
        (6, 11),  # G12
        (9, 11),  # J12
        # Третий ряд (row 22)
        (0, 22),  # A23
        (3, 22),  # D23
        (6, 22),  # G23
        (9, 22),  # J23
    ]
    
    users = []
    
    for user_index, (col, row) in enumerate(user_positions):
        # Фамилия участника
        try:
            full_name = all_values[row][col] if row < len(all_values) and col < len(all_values[row]) else ""
        except IndexError:
            full_name = ""
        
        if not full_name or not full_name.strip():
            continue  # Пропускаем пустые ячейки
        
        last_name, first_name = parse_name(full_name)
        
        # 10 заданий под фамилией
        tasks = []
        for i in range(10):
            task_row = row + 1 + i
            try:
                description = all_values[task_row][col] if task_row < len(all_values) and col < len(all_values[task_row]) else ""
                # Статус справа от задания
                status_col = col + 1
                status = all_values[task_row][status_col] if task_row < len(all_values) and status_col < len(all_values[task_row]) else ""
                completed = is_completed(status)
            except IndexError:
                description = ""
                completed = False
            
            tasks.append(TaskData(
                number=i + 1,
                description=description.strip() if description else f"Индивидуальное задание {i + 1}",
                is_completed=completed
            ))
        
        users.append(UserData(
            last_name=last_name,
            first_name=first_name,
            command_number=command_number,
            sheet_index=user_index,
            tasks=tasks
        ))
        print(f"    👤 {last_name} {first_name} [idx={user_index}]: {sum(1 for t in tasks if t.is_completed)}/10 выполнено")
    
    return users


def parse_all(spreadsheet_id: str) -> list[CommandData]:
    """
    Парсинг всей таблицы.
    
    Returns:
        Список команд с участниками и заданиями
    """
    print("🔄 Начинаем парсинг Google Sheets...")
    print(f"📊 ID таблицы: {spreadsheet_id}\n")
    
    client = get_google_client()
    spreadsheet = client.open_by_key(spreadsheet_id)
    
    # 1. Парсим лист "команды"
    commands_sheet = spreadsheet.worksheet("команды")
    commands = parse_commands_sheet(commands_sheet)
    
    time.sleep(RATE_LIMIT_DELAY)  # Пауза для rate limit
    
    # 2. Парсим листы участников (1-10)
    for cmd_num in range(1, 11):
        try:
            users_sheet = spreadsheet.worksheet(str(cmd_num))
            users = parse_users_sheet(users_sheet, cmd_num)
            
            if cmd_num in commands:
                commands[cmd_num].users = users
            
            time.sleep(RATE_LIMIT_DELAY)  # Пауза для rate limit
            
        except gspread.exceptions.WorksheetNotFound:
            print(f"  ⚠️ Лист '{cmd_num}' не найден, пропускаем")
            continue
    
    return list(commands.values())


def save_to_json(data: list[CommandData], output_path: Path):
    """Сохранить данные в JSON файл."""
    # Конвертируем dataclass в dict
    json_data = [asdict(cmd) for cmd in data]
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 Данные сохранены в: {output_path}")


def main():
    """Точка входа скрипта."""
    parser = argparse.ArgumentParser(description="Парсер Google Sheets")
    parser.add_argument(
        "--test", 
        action="store_true", 
        help="Тестовый режим: сохранить результат в JSON"
    )
    parser.add_argument(
        "--sheet-id",
        type=str,
        help="ID Google таблицы (или из .env)"
    )
    args = parser.parse_args()
    
    # Получаем ID таблицы
    spreadsheet_id = args.sheet_id
    if not spreadsheet_id:
        try:
            from config import get_settings
            spreadsheet_id = get_settings().google_sheet_id
        except Exception:
            pass
    
    if not spreadsheet_id:
        print("❌ Укажи ID таблицы через --sheet-id или в .env (GOOGLE_SHEET_ID)")
        return
    
    try:
        # Парсим данные
        data = parse_all(spreadsheet_id)
        
        # Статистика
        print("\n" + "="*50)
        print("📊 ИТОГО:")
        total_users = sum(len(cmd.users) for cmd in data)
        total_cmd_tasks = sum(len(cmd.tasks) for cmd in data)
        total_user_tasks = sum(len(u.tasks) for cmd in data for u in cmd.users)
        
        print(f"  • Команд: {len(data)}")
        print(f"  • Участников: {total_users}")
        print(f"  • Командных заданий: {total_cmd_tasks}")
        print(f"  • Индивидуальных заданий: {total_user_tasks}")
        
        if args.test:
            # Тестовый режим - сохраняем в JSON
            output_path = PROJECT_ROOT / "parsed_data.json"
            save_to_json(data, output_path)
        else:
            print("\n✅ Парсинг завершён! Данные готовы для импорта в БД.")
            return data
            
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        raise


if __name__ == "__main__":
    main()

