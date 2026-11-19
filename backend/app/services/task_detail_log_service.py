"""任务明细日志服务。

- new_batch()        生成一次执行的批次ID
- write_detail()     写入一步明细（独立会话，保证主流程回滚时明细仍在）
- format_detail_text() 把明细格式化成文本框展示文本
- trim_details()     超过保留上限时删除最旧记录
- ensure_table()     启动时确保表存在（无需手动跑 init_db）
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal, engine
from app.models.task_detail_log import TaskDetailLog

# 步骤中文名，用于文本框展示
STEP_LABELS = {
    "task_start": "任务开始",
    "verify_login": "验证登录态",
    "feed_start": "开始更新公众号",
    "fetch_start": "开始执行拉取",
    "fetched": "已拉取",
    "no_update": "无需更新",
    "error": "拉取出错",
    "warning": "提醒",
    "task_end": "任务结束",
}

# 任务类型中文名
TASK_TYPE_LABELS = {
    "job": "定时任务",
    "latest": "最新拉取",
    "history": "历史记录",
}


def new_batch() -> str:
    """批次ID：时间戳 + 随机串，便于按批次回溯一次完整执行。"""
    return datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]


def _truncate(value: Any, limit: int = 4000) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if len(text) <= limit else text[:limit] + "...(已截断)"


def write_detail(
    *,
    batch_id: str,
    task_type: str = "job",
    job_id: int | None = None,
    job_name: str = "",
    wxs_id: str = "",
    feed_name: str = "",
    step: str = "",
    message: str = "",
    level: str = "info",
    success: bool = True,
    error_msg: Any = None,
) -> TaskDetailLog | None:
    """写入一步明细。独立开会话，确保主流程异常回滚时明细仍保留。"""
    session = SessionLocal()
    try:
        entry = TaskDetailLog(
            batch_id=batch_id or new_batch(),
            task_type=task_type,
            job_id=job_id,
            job_name=job_name or "",
            wxs_id=wxs_id or "",
            feed_name=feed_name or "",
            step=step,
            message=message or "",
            level=level,
            success=1 if success else 0,
            error_msg=_truncate(error_msg),
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)
        trim_details(session)
        return entry
    except Exception:
        # 明细日志写入失败绝不能影响主流程
        session.rollback()
        return None
    finally:
        session.close()


def trim_details(session=None) -> None:
    """超过保留上限时删除最旧记录。"""
    own = session is None
    session = session or SessionLocal()
    try:
        keep = settings.LOG_DETAIL_KEEP
        total = session.query(TaskDetailLog).count()
        if total > keep:
            ids = [
                row.id
                for row in session.query(TaskDetailLog.id)
                .order_by(TaskDetailLog.id.asc())
                .limit(total - keep)
                .all()
            ]
            if ids:
                session.query(TaskDetailLog).filter(TaskDetailLog.id.in_(ids)).delete(
                    synchronize_session=False
                )
                session.commit()
    finally:
        if own:
            session.close()


def _fmt_time(value: datetime | None) -> str:
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


def format_detail_text(rows: list[TaskDetailLog], by_batch: bool = True) -> str:
    """把明细记录格式化成文本框展示文本。

    by_batch=True 时按批次分组，便于回溯一次完整任务；否则按时间逐行输出。
    """
    if not rows:
        return "（暂无任务明细日志）"

    lines: list[str] = []
    current_batch: str | None = None
    for row in rows:
        batch = row.batch_id or "-"
        if by_batch and batch != current_batch:
            current_batch = batch
            type_label = TASK_TYPE_LABELS.get(row.task_type, row.task_type)
            name = row.job_name or "任务"
            lines.append("")
            lines.append("=" * 72)
            lines.append(f"批次 {batch}  [{type_label}] {name}")
            lines.append("=" * 72)

        step_label = STEP_LABELS.get(row.step, row.step)
        level_mark = {"info": "", "warning": "[提醒]", "error": "[错误]"}.get(
            row.level, ""
        )
        name = f"｜{row.feed_name}" if row.feed_name else ""
        prefix = f"[{_fmt_time(row.create_time)}] {step_label}{name} {level_mark}".rstrip()
        lines.append(prefix)
        if row.message:
            lines.append(f"    {row.message}")
        if row.error_msg:
            lines.append(f"    异常原因: {row.error_msg}")

    return "\n".join(lines).lstrip("\n")


def query_details(
    *,
    task_type: str | None = None,
    batch_id: str | None = None,
    limit: int = 100,
) -> list[TaskDetailLog]:
    """按条件查询明细（最新在前，调用方可反转为时间正序展示）。"""
    with SessionLocal() as session:
        stmt = select(TaskDetailLog)
        if task_type:
            stmt = stmt.where(TaskDetailLog.task_type == task_type)
        if batch_id:
            stmt = stmt.where(TaskDetailLog.batch_id == batch_id)
        stmt = stmt.order_by(TaskDetailLog.id.desc()).limit(limit)
        return list(session.scalars(stmt).all())


def clear_details() -> int:
    """清空全部明细日志，返回删除条数。"""
    with SessionLocal() as session:
        count = session.query(TaskDetailLog).count()
        session.query(TaskDetailLog).delete(synchronize_session=False)
        session.commit()
        return count


def ensure_table() -> None:
    """启动时确保明细表存在（已有数据库也能自动建表，免手动 init_db）。"""
    TaskDetailLog.__table__.create(bind=engine, checkfirst=True)
