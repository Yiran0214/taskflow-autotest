"""统计模块: 任务看板汇总数据"""
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Task, TaskStatus, User
from app.routers.users import get_current_user
from app.schemas import StatsSummary

router = APIRouter(prefix="/api/v1/stats", tags=["stats"])


@router.get("/summary", response_model=StatsSummary)
def summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """统计当前用户任务: 各状态数量、逾期数、完成率"""
    cond = Task.user_id == current_user.id
    total = db.scalar(select(func.count()).select_from(Task).where(cond)) or 0
    by_status = dict(
        db.execute(
            select(Task.status, func.count()).where(cond).group_by(Task.status)
        ).all()
    )
    # 逾期: 截止日期早于今天且尚未完成
    overdue = (
        db.scalar(
            select(func.count())
            .select_from(Task)
            .where(cond, Task.due_date < date.today(), Task.status != TaskStatus.DONE)
        )
        or 0
    )
    done = by_status.get(TaskStatus.DONE, 0)
    return StatsSummary(
        total=total,
        pending=by_status.get(TaskStatus.PENDING, 0),
        in_progress=by_status.get(TaskStatus.IN_PROGRESS, 0),
        done=done,
        overdue=overdue,
        completion_rate=round(done / total, 4) if total else 0.0,
    )
