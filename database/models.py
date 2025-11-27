from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, BigInteger, Text, ForeignKey, Boolean


class Base(DeclarativeBase):
    __abstract__ = True


class User(Base):
    """Участник команды."""
    __tablename__ = 'users'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    first_name: Mapped[str] = mapped_column(String(255))  # Имя
    last_name: Mapped[str] = mapped_column(String(255))   # Фамилия
    
    tg_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, nullable=True)
    tg_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Баллы участника (за выполнение своих индивидуальных заданий)
    score: Mapped[int] = mapped_column(Integer, default=0)
    
    # Позиция на листе Google Sheets (0-11)
    sheet_index: Mapped[int] = mapped_column(Integer, default=0)
    
    # Связь с командой
    command_id: Mapped[int] = mapped_column(ForeignKey('commands.id'))
    command: Mapped["Command"] = relationship(back_populates="users")
    
    # Индивидуальные задания участника
    tasks: Mapped[list["UserTask"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    
    @property
    def full_name(self) -> str:
        """Фамилия Имя."""
        return f"{self.last_name} {self.first_name}"


class Command(Base):
    """Команда."""
    __tablename__ = 'commands'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    number: Mapped[int] = mapped_column(Integer, unique=True)  # Номер команды
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Название команды (опционально)
    
    # Баллы команды (только за командные задания, +3 за каждое)
    score: Mapped[int] = mapped_column(Integer, default=0)
    
    # Участники команды
    users: Mapped[list["User"]] = relationship(back_populates="command", cascade="all, delete-orphan")
    
    # Командные задания
    tasks: Mapped[list["CommandTask"]] = relationship(back_populates="command", cascade="all, delete-orphan")
    
    @property
    def total_score(self) -> int:
        """Общий счёт команды = баллы команды + сумма баллов всех участников."""
        return self.score + sum(user.score for user in self.users)


class CommandTask(Base):
    """Командное задание (7 штук на команду)."""
    __tablename__ = 'command_tasks'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Связь с командой
    command_id: Mapped[int] = mapped_column(ForeignKey('commands.id'))
    command: Mapped["Command"] = relationship(back_populates="tasks")
    
    # Номер задания (1-7)
    task_number: Mapped[int] = mapped_column(Integer)
    
    # Описание задания
    description: Mapped[str] = mapped_column(Text)
    
    # Выполнено ли задание
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)


class UserTask(Base):
    """Индивидуальное задание участника (10 штук на участника)."""
    __tablename__ = 'user_tasks'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Связь с участником
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    user: Mapped["User"] = relationship(back_populates="tasks")
    
    # Номер задания (1-10)
    task_number: Mapped[int] = mapped_column(Integer)
    
    # Описание задания
    description: Mapped[str] = mapped_column(Text)
    
    # Выполнено ли задание
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
