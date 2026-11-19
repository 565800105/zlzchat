"""统一响应结构与业务异常。

成功响应统一为 {"code": 200, "msg": "ok", "data": ...}
失败响应统一为 {"code": <非200>, "msg": <原因>, "data": null}
"""
from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class ApiException(Exception):
    """业务异常，由全局异常处理器转为统一响应。"""

    def __init__(self, msg: str, code: int = 400):
        self.msg = msg
        self.code = code
        super().__init__(msg)


def ok(data: Any = None, msg: str = "ok") -> dict[str, Any]:
    """成功响应体。"""
    return {"code": 200, "msg": msg, "data": data}


def page_result(
    rows: list, total: int, page_num: int, page_size: int
) -> dict[str, Any]:
    """分页响应体。"""
    return ok(
        {
            "list": rows,
            "total": total,
            "pageNum": page_num,
            "pageSize": page_size,
        }
    )


def fail(msg: str, code: int = 400) -> dict[str, Any]:
    """失败响应体（供视图内直接返回）。"""
    return {"code": code, "msg": msg, "data": None}


async def api_exception_handler(_: Request, exc: ApiException) -> JSONResponse:
    """把 ApiException 转成统一 JSON 响应。"""
    return JSONResponse(
        status_code=200,
        content={"code": exc.code, "msg": exc.msg, "data": None},
    )
