"""订阅源分类及明细模型（对应 sys_mp_classification / sys_mp_classification_detail）。"""
from __future__ import annotations

from sqlalchemy import BigInteger, Integer, String

_PkBigInt = BigInteger().with_variant(Integer, "sqlite")
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base


class CnvpMpClassification(Base, AuditMixin):
    __tablename__ = "sys_mp_classification"
    __table_args__ = {"comment": "订阅源分类表"}

    classification_id: Mapped[int] = mapped_column(
        _PkBigInt, primary_key=True, autoincrement=True, comment="分类ID"
    )
    classification_name: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="分类名称")
    show_count: Mapped[int] = mapped_column(Integer, default=20, comment="显示条数")
    icon: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="图标")
    is_deleted: Mapped[int] = mapped_column(Integer, default=0, comment="逻辑删除 0正常 1删除")
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="备注")


class CnvpMpClassificationDetail(Base, AuditMixin):
    __tablename__ = "sys_mp_classification_detail"
    __table_args__ = {"comment": "订阅源分类明细表"}

    classification_detai_id: Mapped[int] = mapped_column(
        _PkBigInt, primary_key=True, autoincrement=True, comment="主键(原表拼写 detai)"
    )
    feed_id: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="所属公众号ID")
    mp_name: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="公众号名称")
    mp_cover: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="公众号封面图")
    wxs_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True, comment="微信读书ID")
    classification_id: Mapped[int] = mapped_column(BigInteger, index=True, comment="分类ID")
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="备注")
