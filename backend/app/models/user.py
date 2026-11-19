"""后台管理员用户模型（对应 sys_user 精简版）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base


class SysUser(Base, AuditMixin):
    __tablename__ = "sys_user"
    __table_args__ = {"comment": "后台管理员用户表"}

    user_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="用户ID")
    user_name: Mapped[str] = mapped_column(String(64), unique=True, index=True, comment="登录用户名")
    nick_name: Mapped[str] = mapped_column(String(64), default="", comment="昵称")
    password: Mapped[str] = mapped_column(String(255), comment="bcrypt 密码哈希")
    status: Mapped[str] = mapped_column(String(1), default="0", comment="状态 0正常 1停用")
    email: Mapped[str | None] = mapped_column(String(128), nullable=True)
    phonenumber: Mapped[str | None] = mapped_column(String(32), nullable=True)
    login_ip: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="最后登录IP")
    login_date: Mapped[datetime | None] = mapped_column(nullable=True, comment="最后登录时间")
