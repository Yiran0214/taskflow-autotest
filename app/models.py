"""ORM 数据模型: 用户 (User) 与任务 (Task)"""
import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class TaskStatus(str, enum.Enum):
    """任务状态: pending(待办) -> in_progress(进行中) -> done(已完成)"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class TaskPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    tasks: Mapped[list["Task"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    priority: Mapped[TaskPriority] = mapped_column(
        # 数据库存储枚举值 ("low"/"medium"/"high") 而非枚举名, 便于直连断言
        Enum(TaskPriority, values_callable=lambda e: [m.value for m in e]),
        default=TaskPriority.MEDIUM,
    )
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, values_callable=lambda e: [m.value for m in e]),
        default=TaskStatus.PENDING,
    )
    due_date: Mapped[date | None] = mapped_column(Date, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )

    owner: Mapped[User] = relationship(back_populates="tasks")
