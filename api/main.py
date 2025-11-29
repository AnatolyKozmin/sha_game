"""
FastAPI для лидерборда команд.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pathlib import Path

from config import get_settings
from database.models import Base, Command, User


# Global
engine = None
async_session_maker = None

# Состояние отображения (скрыто/показано)
display_state = {
    "hidden": True,  # По умолчанию скрыто
    "timer_end": None,  # Время окончания таймера
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan."""
    global engine, async_session_maker
    
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    yield
    
    await engine.dispose()


app = FastAPI(
    title="Leaderboard API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_session():
    """Get DB session."""
    async with async_session_maker() as session:
        yield session


@app.get("/api/leaderboard")
async def get_leaderboard(session: AsyncSession = Depends(get_session)):
    """Получить лидерборд команд."""
    result = await session.execute(
        select(Command)
        .options(selectinload(Command.users))
        .order_by(Command.number)
    )
    commands = result.scalars().all()
    
    # Считаем total_score и сортируем
    leaderboard = []
    for cmd in commands:
        users_score = sum(u.score for u in cmd.users)
        total = cmd.score + users_score
        leaderboard.append({
            "id": cmd.id,
            "number": cmd.number,
            "name": cmd.name or f"Команда {cmd.number}",
            "team_score": cmd.score,
            "users_score": users_score,
            "total_score": total,
            "members_count": len(cmd.users),
        })
    
    # Сортируем по total_score
    leaderboard.sort(key=lambda x: x["total_score"], reverse=True)
    
    # Добавляем rank
    for i, item in enumerate(leaderboard):
        item["rank"] = i + 1
    
    return {"leaderboard": leaderboard, "hidden": display_state["hidden"]}


@app.get("/api/users")
async def get_top_users(limit: int = 10, session: AsyncSession = Depends(get_session)):
    """
    Топ участников по личным баллам.
    
    Логика сортировки:
    1. По личным баллам — убывание
    2. Если личные равны И оба = 10 (максимум), по баллам команды — убывание
    3. Если и командные равны, кто раньше набрал максимум — выше
    """
    # Загружаем пользователей с командами
    result = await session.execute(
        select(User)
        .options(selectinload(User.command))
    )
    users = result.scalars().all()
    
    MAX_PERSONAL = 10  # Максимум личных баллов
    
    def sort_key(user: User):
        personal = user.score
        team_score = user.command.score
        
        # Приоритет 1: личные баллы (убывание)
        priority1 = -personal
        
        # Приоритет 2: если личные = 10, то по командным баллам (убывание)
        if personal == MAX_PERSONAL:
            priority2 = -team_score
        else:
            priority2 = 0
        
        # Приоритет 3: если личные = 10 и равные командные, по времени достижения
        if personal == MAX_PERSONAL:
            if user.max_reached_at:
                priority3 = user.max_reached_at.timestamp()
            else:
                priority3 = float('inf')  # Если не записано — в конец
        else:
            priority3 = 0
        
        return (priority1, priority2, priority3)
    
    # Сортируем
    sorted_users = sorted(users, key=sort_key)[:limit]
    
    return {
        "users": [
            {
                "rank": i + 1,
                "id": u.id,
                "name": u.full_name,
                "score": u.score,
                "team_number": u.command.number,
                "team_name": u.command.name or f"Команда {u.command.number}",
            }
            for i, u in enumerate(sorted_users)
        ],
        "hidden": display_state["hidden"]
    }


@app.get("/api/display-state")
async def get_display_state():
    """Получить текущее состояние отображения."""
    return display_state


@app.post("/api/display-state")
async def set_display_state(hidden: bool = True, timer_minutes: int = 0):
    """Установить состояние отображения."""
    import time
    display_state["hidden"] = hidden
    if timer_minutes > 0:
        display_state["timer_end"] = time.time() + (timer_minutes * 60)
    else:
        display_state["timer_end"] = None
    return display_state


@app.post("/api/reveal")
async def reveal_names():
    """Показать имена."""
    display_state["hidden"] = False
    display_state["timer_end"] = None
    return display_state


@app.post("/api/hide")
async def hide_names():
    """Скрыть имена."""
    display_state["hidden"] = True
    display_state["timer_end"] = None
    return display_state


@app.get("/api/team/{team_id}")
async def get_team_details(team_id: int, session: AsyncSession = Depends(get_session)):
    """Детали команды с участниками."""
    result = await session.execute(
        select(Command)
        .options(selectinload(Command.users))
        .where(Command.id == team_id)
    )
    command = result.scalar_one_or_none()
    
    if not command:
        return {"error": "Team not found"}
    
    users_data = [
        {
            "id": u.id,
            "name": u.full_name,
            "score": u.score,
        }
        for u in sorted(command.users, key=lambda x: x.score, reverse=True)
    ]
    
    return {
        "id": command.id,
        "number": command.number,
        "name": command.name or f"Команда {command.number}",
        "team_score": command.score,
        "users_score": sum(u.score for u in command.users),
        "total_score": command.score + sum(u.score for u in command.users),
        "users": users_data,
    }


# Serve frontend
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
FONTS_DIR = FRONTEND_DIR / "fonts"

# Serve fonts
if FONTS_DIR.exists():
    app.mount("/fonts", StaticFiles(directory=FONTS_DIR), name="fonts")

@app.get("/")
async def serve_index():
    """Главная страница - редирект на команды."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/teams")

@app.get("/teams")
async def serve_teams():
    """Страница топ-10 команд."""
    file = FRONTEND_DIR / "teams.html"
    if file.exists():
        return FileResponse(file)
    return {"error": "teams.html not found"}

@app.get("/users")
async def serve_users():
    """Страница топ-5 участников."""
    file = FRONTEND_DIR / "users.html"
    if file.exists():
        return FileResponse(file)
    return {"error": "users.html not found"}


@app.get("/admin")
async def serve_admin():
    """Админ-панель."""
    file = FRONTEND_DIR / "admin.html"
    if file.exists():
        return FileResponse(file)
    return {"error": "admin.html not found"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)

