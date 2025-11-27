"""
Модуль для обновления Google Sheets при изменении статуса заданий.
"""

from pathlib import Path
import gspread
from gspread.utils import rowcol_to_a1
from google.oauth2.service_account import Credentials


PROJECT_ROOT = Path(__file__).parent.parent
CREDENTIALS_PATH = PROJECT_ROOT / "credentials.json"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Цвета для ячеек
GREEN_COLOR = {"red": 0.56, "green": 0.93, "blue": 0.56}  # Светло-зелёный
WHITE_COLOR = {"red": 1, "green": 1, "blue": 1}  # Белый


def get_google_client() -> gspread.Client:
    """Инициализация клиента Google Sheets с правами на запись."""
    if not CREDENTIALS_PATH.exists():
        raise FileNotFoundError(f"credentials.json не найден: {CREDENTIALS_PATH}")
    
    creds = Credentials.from_service_account_file(
        str(CREDENTIALS_PATH),
        scopes=SCOPES
    )
    return gspread.authorize(creds)


# ============ ПОЗИЦИИ КОМАНД НА ЛИСТЕ "команды" ============
# (col, row) - колонка и строка заголовка команды (0-indexed)
COMMAND_POSITIONS = {
    1: (0, 0),    # A1
    2: (3, 0),    # D1
    3: (7, 0),    # H1
    4: (11, 0),   # L1
    5: (15, 0),   # P1
    6: (0, 8),    # A9
    7: (3, 8),    # D9
    8: (7, 8),    # H9
    9: (11, 8),   # L9
    10: (15, 8),  # P9
}

# ============ ПОЗИЦИИ УЧАСТНИКОВ НА ЛИСТАХ 1-10 ============
# Индекс участника -> (col, row) его фамилии
# 12 участников на команду: 4 колонки × 3 ряда
USER_POSITIONS = [
    (0, 0),   # A1 - участник 0
    (3, 0),   # D1 - участник 1
    (6, 0),   # G1 - участник 2
    (9, 0),   # J1 - участник 3
    (0, 11),  # A12 - участник 4
    (3, 11),  # D12 - участник 5
    (6, 11),  # G12 - участник 6
    (9, 11),  # J12 - участник 7
    (0, 22),  # A23 - участник 8
    (3, 22),  # D23 - участник 9
    (6, 22),  # G23 - участник 10
    (9, 22),  # J23 - участник 11
]


def get_command_task_cell(command_number: int, task_number: int) -> tuple[int, int]:
    """
    Получить позицию ячейки статуса командного задания.
    
    Returns:
        (row, col) - 1-indexed для gspread
    """
    if command_number not in COMMAND_POSITIONS:
        raise ValueError(f"Неверный номер команды: {command_number}")
    
    col, row = COMMAND_POSITIONS[command_number]
    # Задания идут под заголовком команды (row + task_number)
    # Статус в колонке справа (col + 1)
    task_row = row + task_number  # 0-indexed
    status_col = col + 1  # 0-indexed
    
    # gspread использует 1-indexed
    return (task_row + 1, status_col + 1)


def get_user_task_cell(user_index: int, task_number: int) -> tuple[int, int]:
    """
    Получить позицию ячейки статуса индивидуального задания.
    
    Args:
        user_index: индекс участника на листе (0-11)
        task_number: номер задания (1-10)
    
    Returns:
        (row, col) - 1-indexed для gspread
    """
    if user_index >= len(USER_POSITIONS):
        raise ValueError(f"Неверный индекс участника: {user_index}")
    
    col, row = USER_POSITIONS[user_index]
    # Задания идут под фамилией (row + task_number)
    # Статус в колонке справа (col + 1)
    task_row = row + task_number  # 0-indexed
    status_col = col + 1  # 0-indexed
    
    # gspread использует 1-indexed
    return (task_row + 1, status_col + 1)


def update_command_task_status(
    spreadsheet_id: str,
    command_number: int,
    task_number: int,
    is_completed: bool
):
    """
    Обновить статус командного задания в Google Sheets.
    """
    client = get_google_client()
    spreadsheet = client.open_by_key(spreadsheet_id)
    worksheet = spreadsheet.worksheet("команды")
    
    row, col = get_command_task_cell(command_number, task_number)
    cell_a1 = rowcol_to_a1(row, col)
    
    if is_completed:
        # Пишем "Сделано" и красим в зелёный
        worksheet.update_acell(cell_a1, "Сделано")
        worksheet.format(cell_a1, {"backgroundColor": GREEN_COLOR})
    else:
        # Очищаем и убираем цвет
        worksheet.update_acell(cell_a1, "")
        worksheet.format(cell_a1, {"backgroundColor": WHITE_COLOR})


def update_user_task_status(
    spreadsheet_id: str,
    command_number: int,
    user_index: int,
    task_number: int,
    is_completed: bool
):
    """
    Обновить статус индивидуального задания в Google Sheets.
    
    Args:
        spreadsheet_id: ID таблицы
        command_number: номер команды (1-10) = название листа
        user_index: индекс участника на листе (0-11)
        task_number: номер задания (1-10)
        is_completed: выполнено или нет
    """
    client = get_google_client()
    spreadsheet = client.open_by_key(spreadsheet_id)
    worksheet = spreadsheet.worksheet(str(command_number))
    
    row, col = get_user_task_cell(user_index, task_number)
    cell_a1 = rowcol_to_a1(row, col)
    
    if is_completed:
        worksheet.update_acell(cell_a1, "Сделано")
        worksheet.format(cell_a1, {"backgroundColor": GREEN_COLOR})
    else:
        worksheet.update_acell(cell_a1, "")
        worksheet.format(cell_a1, {"backgroundColor": WHITE_COLOR})

