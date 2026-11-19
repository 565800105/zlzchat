"""公众号信息模型（对应 sys_feeds）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base


class CnvpFeeds(Base, AuditMixin):
    __tablename__ = "sys_feeds"
    __table_args__ = (
        # 自动拉取过滤（status=2）
        Index("idx_sys_feeds_status", "status"),
        {"comment": "公众号信息表"},
    )

    feed_id: Mapped[str] = mapped_column(String(50), primary_key=True, comment="主键(UUID)")
    wxs_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True, comment="微信读书ID")
    mp_name: Mapped[str] = mapped_column(String(512), comment="公众号名称")
    mp_cover: Mapped[str] = mapped_column(String(500), default="", comment="公众号封面图")
    mp_intro: Mapped[str] = mapped_column(Text, default="", comment="公众号简介")
    status: Mapped[int] = mapped_column(Integer, default=2, comment="状态 1不拉取 2自动拉取")
    sync_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="最后更新时间")
    show_count: Mapped[int] = mapped_column(Integer, default=20, comment="显示数量")
    update_count: Mapped[int] = mapped_column(Integer, default=0, comment="更新次数")
    version: Mapped[str | None] = mapped_column(
        "remark", String(500), nullable=True, comment="版本号(原表 remark 字段，用于增量判断)"
    )
    is_deleted: Mapped[int] = mapped_column(Integer, default=0, comment="逻辑删除 0正常 1删除")
