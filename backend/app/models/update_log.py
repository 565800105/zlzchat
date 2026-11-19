"""更新记录模型（对应 sys_update_log）。"""
from __future__ import annotations

from sqlalchemy import BigInteger, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base

_PkBigInt = BigInteger().with_variant(Integer, "sqlite")


class CnvpUpdateLog(Base, AuditMixin):
    __tablename__ = "sys_update_log"
    __table_args__ = (
        # 定时任务防重：查 log_catagory=1 & log_sta=1 的执行中记录
        Index("idx_sys_update_log_cat_sta", "log_catagory", "log_sta"),
        Index("idx_sys_update_log_create_time", "create_time"),
        {"comment": "更新记录表"},
    )

    log_id: Mapped[int] = mapped_column(_PkBigInt, primary_key=True, autoincrement=True, comment="主键")
    log_sta: Mapped[str | None] = mapped_column(String(2), nullable=True, comment="状态 1执行中 2执行结束")
    log_result_sta: Mapped[str | None] = mapped_column(String(2), nullable=True, comment="结果 1正常 2异常")
    log_catagory: Mapped[str | None] = mapped_column(
        String(2), nullable=True, comment="类别 1定时任务 2最新同步 3历史更新"
    )
    update_num: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="更新数量")
    feed_name: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="公众号名称")
    history_start_num: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="历史起始序号")
    history_end_num: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="历史结束序号")
    is_deleted: Mapped[int] = mapped_column(Integer, default=0, comment="逻辑删除 0正常 1删除")
    remark: Mapped[str | None] = mapped_column(String(5000), nullable=True, comment="备注/异常原因")
