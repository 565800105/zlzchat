"""账号配置模型（对应 sys_accounts）。"""
from __future__ import annotations

from sqlalchemy import BigInteger, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base


class CnvpAccounts(Base, AuditMixin):
    __tablename__ = "sys_accounts"
    __table_args__ = {"comment": "账号配置表（微信公众号登录信息）"}

    accounts_id: Mapped[str] = mapped_column(String(255), primary_key=True, comment="主键(UUID)")
    cookie_value: Mapped[str | None] = mapped_column(String(4000), nullable=True, comment="Cookie/JWT")
    nick_name: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="账号昵称")
    status: Mapped[int] = mapped_column(Integer, default=1, comment="账号状态 1正常 2禁用 3风控")
    category: Mapped[str | None] = mapped_column(String(1), nullable=True, comment="账号类型 1微信 2抖音 3小红书")
    is_deleted: Mapped[int] = mapped_column(Integer, default=0, comment="逻辑删除 0正常 1删除")
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="备注")
