from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

# ID проверяющих (добавь сюда Telegram ID проверяющих)
CHECKER_IDS: set[int] = {
    922109605
    # 987654321,
}


class CheckerFilter(BaseFilter):
    """Фильтр: пропускает только проверяющих."""
    
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user_id = event.from_user.id
        return user_id in CHECKER_IDS


def is_checker(user_id: int) -> bool:
    """Проверить, является ли пользователь проверяющим."""
    return user_id in CHECKER_IDS

