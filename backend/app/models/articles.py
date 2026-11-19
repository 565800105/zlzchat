"""文章信息模型（对应 sys_mp_articles）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base


class CnvpMpArticles(Base, AuditMixin):
    __tablename__ = "sys_mp_articles"
    __table_args__ = (
        # 大数据量高频查询：按公众号+未删除+发布时间排序；全部未删除按发布时间排序
        Index("idx_sys_articles_wxs_deleted_time", "wxs_id", "is_deleted", "publish_time"),
        Index("idx_sys_articles_deleted_time", "is_deleted", "publish_time"),
        Index("idx_sys_articles_original", "original_id"),
        {"comment": "文章信息表"},
    )

    articles_id: Mapped[str] = mapped_column(String(50), primary_key=True, comment="主键(UUID)")
    original_id: Mapped[str] = mapped_column(String(80), comment="原文ID")
    wxs_id: Mapped[str] = mapped_column(String(100), index=True, comment="微信读书ID")
    title: Mapped[str] = mapped_column(String(400), default="", comment="标题")
    links: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="文章链接")
    doc_url: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="文档地址")
    pic_url: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="封面图")
    publish_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True, comment="发布时间")
    content: Mapped[str | None] = mapped_column(Text, nullable=True, comment="富文本内容")
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True, comment="纯文本")
    read_type: Mapped[str] = mapped_column(String(5), default="0", comment="阅读类型")
    is_deleted: Mapped[int] = mapped_column(Integer, default=0, comment="逻辑删除 0正常 1删除")
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="备注")
