"""日志查询接口 /api/admin/logs（后台只看最新日志情况）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models.base import to_dicts
from app.models.request_log import RequestLog
from app.models.user import SysUser
from app.response import ok
from app.services import task_detail_log_service as detail_svc

router = APIRouter(prefix="/admin/logs", tags=["日志"])


@router.get("/list")
def list_logs(
    logType: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    onlyFailed: bool = False,
    db: Session = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    """返回最新的日志（默认最多 50 条），异常排在查看范围内最直观。"""
    stmt = select(RequestLog)
    if logType:
        stmt = stmt.where(RequestLog.log_type == logType)
    if onlyFailed:
        stmt = stmt.where(RequestLog.success == 0)
    stmt = stmt.order_by(RequestLog.id.desc()).limit(limit)
    rows = db.scalars(stmt).all()
    return ok(to_dicts(rows))


@router.get("/stats")
def log_stats(db: Session = Depends(get_db), _: SysUser = Depends(get_current_user)):
    """简易统计：各类型数量与失败数，便于直观看到异常。"""
    from sqlalchemy import func

    total = db.query(func.count(RequestLog.id)).scalar() or 0
    failed = db.query(func.count(RequestLog.id)).filter(RequestLog.success == 0).scalar() or 0
    return ok({"total": total, "failed": failed, "keepRecent": settings.LOG_KEEP_RECENT})


# ======================== 任务明细日志 ========================
# 以 batch_id 串起一次任务执行的每一步，前端用文本框展示，便于出错回溯。


@router.get("/detail-list")
def detail_log_list(
    taskType: str | None = None,
    batchId: str | None = None,
    limit: int = Query(100, ge=1, le=2000),
    _: SysUser = Depends(get_current_user),
):
    """结构化返回任务明细（最新在前）。"""
    rows = detail_svc.query_details(
        task_type=taskType or None, batch_id=batchId or None, limit=limit
    )
    return ok(to_dicts(rows))


@router.get("/detail-text")
def detail_log_text(
    taskType: str | None = None,
    limit: int = Query(100, ge=1, le=2000),
    _: SysUser = Depends(get_current_user),
):
    """返回格式化文本，供前端文本框直接展示。按批次分组，按时间正序输出。"""
    rows = detail_svc.query_details(task_type=taskType or None, limit=limit)
    rows = list(reversed(rows))  # 转正序，符合阅读习惯
    return ok(
        {
            "text": detail_svc.format_detail_text(rows, by_batch=True),
            "count": len(rows),
            "limit": settings.LOG_DETAIL_KEEP,
        }
    )


@router.post("/detail-clear")
def detail_log_clear(_: SysUser = Depends(get_current_user)):
    """清空任务明细日志。"""
    count = detail_svc.clear_details()
    return ok(msg=f"已清空 {count} 条明细日志")
