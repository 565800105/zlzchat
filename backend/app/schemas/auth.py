"""鉴权相关 Pydantic 模型。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64, description="用户名")
    password: str = Field(min_length=1, description="密码")


class PasswordChangeIn(BaseModel):
    old_password: str = Field(min_length=1, description="原密码")
    new_password: str = Field(min_length=6, description="新密码(至少6位)")
