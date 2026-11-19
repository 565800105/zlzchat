"""任务明细日志模型。

与"日志查看"里的 sys_request_log（请求/任务概要）不同，本表以 batch_id
串起一次任务执行的每一步，用于出错回溯：定时任务开始、验证登录态、开始更新
某公众号、开始拉取、已拉取多少条、无需更新、拉取出错、任务结束等。

覆盖三类执行路径（task_type）：
- job     定时任务更新
- latest  最新拉取
- history 历史记录
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TaskDetailLog(Base):
    __tablename__ = "sys_task_detail_log"
    __table_args__ = {"comment": "任务明细日志表(逐步回溯)"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(
        String(64), default="", index=True, comment="批次ID：串起一次任务执行的全部步骤"
    )
    task_type: Mapped[str] = mapped_column(
        String(16), default="job", index=True, comment="任务类型 job/latest/history"
    )
    job_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="定时任务ID")
    job_name: Mapped[str] = mapped_column(
        String(128), default="", comment="任务/操作名称"
    )
    wxs_id: Mapped[str] = mapped_column(String(64), default="", comment="公众号ID")
    feed_name: Mapped[str] = mapped_column(String(128), default="", comment="公众号名称")
    step: Mapped[str] = mapped_column(
        String(32), default="", index=True, comment="步骤标识 task_start/verify_login/feed_start/fetch_start/fetched/no_update/error/task_end"
    )
    message: Mapped[str] = mapped_column(Text, default="", comment="明细文本(文本框展示内容)")
    level: Mapped[str] = mapped_column(
        String(10), default="info", comment="级别 info/warning/error"
    )
    success: Mapped[int] = mapped_column(Integer, default=1, comment="该步骤是否成功 1是 0否")
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True, comment="异常原因")
    create_time: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, index=True, comment="步骤时间"
    )
