"""请求与任务执行日志模型（后台"只看最新日志"）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RequestLog(Base):
    __tablename__ = "sys_request_log"
    __table_args__ = {"comment": "请求/任务执行日志表"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    log_type: Mapped[str] = mapped_column(
        String(16), default="request", index=True, comment="日志类型 request/job/login"
    )
    method: Mapped[str | None] = mapped_column(String(10), nullable=True, comment="请求方法")
    url: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="请求路径")
    description: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="操作描述")
    user_name: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="操作人")
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="IP地址")
    request_params: Mapped[str | None] = mapped_column(Text, nullable=True, comment="请求参数(截断)")
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="HTTP状态码/业务码")
    success: Mapped[int] = mapped_column(Integer, default=1, comment="是否成功 1是 0否")
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True, comment="异常原因")
    cost_time: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="耗时(ms)")
    create_time: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, index=True, comment="日志时间"
    )
