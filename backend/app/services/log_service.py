"""日志服务：所有请求与定时任务执行都通过这里落库，后台只看最新若干条。"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.request_log import RequestLog


def _truncate(value: Any, limit: int = 2000) -> str | None:
    """把任意参数安全地转成截断字符串，避免日志过大。"""
    if value is None:
        return None
    text = str(value)
    return text if len(text) <= limit else text[:limit] + "...(已截断)"


def write_log(
    *,
    log_type: str = "request",
    method: str | None = None,
    url: str | None = None,
    description: str | None = None,
    user_name: str | None = None,
    ip: str | None = None,
    request_params: Any = None,
    status_code: int | None = None,
    success: bool = True,
    error_msg: Any = None,
    cost_time: int | None = None,
    db: Session | None = None,
) -> RequestLog:
    """写入一条日志。传入 db 则复用会话，否则独立开会话（保证请求回滚时日志仍保留）。"""
    own_session = db is None
    session = db or SessionLocal()
    try:
        entry = RequestLog(
            log_type=log_type,
            method=method,
            url=url,
            description=description,
            user_name=user_name,
            ip=ip,
            request_params=_truncate(request_params),
            status_code=status_code,
            success=1 if success else 0,
            error_msg=_truncate(error_msg, 4000),
            cost_time=cost_time,
        )
        session.add(entry)
        session.commit()
        if own_session:
            session.refresh(entry)
        _trim_logs(session)
        return entry
    finally:
        if own_session:
            session.close()


def _trim_logs(session: Session) -> None:
    """后台只看最新日志：超过上限时删除最旧的记录。"""
    keep = settings.LOG_KEEP_RECENT
    total = session.query(RequestLog).count()
    if total > keep:
        ids = [
            row.id
            for row in session.query(RequestLog.id)
            .order_by(RequestLog.id.asc())
            .limit(total - keep)
            .all()
        ]
        if ids:
            session.query(RequestLog).filter(RequestLog.id.in_(ids)).delete(
                synchronize_session=False
            )
            session.commit()
