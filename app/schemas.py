"""Pydantic 请求/响应模型: 入参校验规则即接口的业务约束"""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import TaskPriority, TaskStatus


class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=20, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(min_length=6, max_length=64)


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: date | None = None


class TaskUpdate(BaseModel):
    """PUT 全量更新: 除 title 外其余字段可选"""

    title: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: date | None = None


class TaskPatch(BaseModel):
    """PATCH 部分更新: 所有字段可选"""

    title: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    priority: TaskPriority | None = None
    due_date: date | None = None

    @field_validator("due_date")
    @classmethod
    def allow_clear_due_date(cls, v):
        """due_date 显式传 null 表示清除截止日期, 这里不做额外限制"""
        return v


class TaskStatusUpdate(BaseModel):
    status: TaskStatus


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    description: str | None
    priority: TaskPriority
    status: TaskStatus
    due_date: date | None
    created_at: datetime
    updated_at: datetime


class TaskListResponse(BaseModel):
    items: list[TaskOut]
    total: int
    page: int
    size: int
    pages: int


class StatsSummary(BaseModel):
    total: int
    pending: int
    in_progress: int
    done: int
    overdue: int
    completion_rate: float
