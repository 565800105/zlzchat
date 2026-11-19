"""定时任务与任务日志模型（对应 sys_job / sys_job_log）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base

_PkBigInt = BigInteger().with_variant(Integer, "sqlite")


class SysJob(Base, AuditMixin):
    __tablename__ = "sys_job"
    __table_args__ = {"comment": "定时任务调度表"}

    job_id: Mapped[int] = mapped_column(_PkBigInt, primary_key=True, autoincrement=True, comment="任务ID")
    job_name: Mapped[str] = mapped_column(String(64), comment="任务名称")
    job_group: Mapped[str] = mapped_column(String(64), default="DEFAULT", comment="任务组名")
    invoke_target: Mapped[str] = mapped_column(
        String(500), default="ZlzChat.updateFeedArticleNew", comment="调用目标字符串(内部固定,不再暴露)"
    )
    cron_expression: Mapped[str] = mapped_column(String(255), comment="cron 表达式")
    misfire_policy: Mapped[str] = mapped_column(String(1), default="3", comment="执行策略 1立即2一次3放弃")
    concurrent: Mapped[str] = mapped_column(String(1), default="1", comment="并发执行 0允许 1禁止")
    status: Mapped[str] = mapped_column(String(1), default="0", comment="状态 0正常 1暂停")
    acount_type: Mapped[str] = mapped_column(
        String(5), default="2", comment="账号策略 1异常切换 2轮询"
    )
    classification_id: Mapped[list | None] = mapped_column(
        JSON, nullable=True, comment="所选分组ID列表"
    )
    wxs_id: Mapped[list | None] = mapped_column(JSON, nullable=True, comment="所选公众号wxs_id列表")
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="备注")


class SysJobLog(Base):
    __tablename__ = "sys_job_log"
    __table_args__ = {"comment": "任务调度日志表"}

    job_log_id: Mapped[int] = mapped_column(_PkBigInt, primary_key=True, autoincrement=True)
    job_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    job_group: Mapped[str | None] = mapped_column(String(64), nullable=True)
    invoke_target: Mapped[str | None] = mapped_column(String(500), nullable=True)
    fire_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="触发时间")
    fire_result: Mapped[str] = mapped_column(String(2), default="0", comment="执行结果 0成功 1失败")
    error_info: Mapped[str | None] = mapped_column(Text, nullable=True, comment="异常信息")
    elapsed_time: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="耗时(ms)")
