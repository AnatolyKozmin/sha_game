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
    
    return {"leaderboard": leaderboard}


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

@app.get("/")
async def serve_frontend():
    """Serve main page."""
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Frontend not found. Place index.html in /frontend/"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)

