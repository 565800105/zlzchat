"""FastAPI 应用入口。

- 统一响应与全局异常处理
- 每个请求的访问日志中间件（自动记录参数、IP、耗时、异常原因）
- CORS、静态资源、定时任务生命周期
"""
from __future__ import annotations

import json
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import (
    accounts,
    articles,
    auth,
    classification,
    feeds,
    job,
    logs,
    open as open_api,
    sys_config,
    update_log,
)
from app.config import BASE_DIR, DATA_DIR, settings
from app.response import ApiException, api_exception_handler, ok
from app.services import scheduler as scheduler_service
from app.services.log_service import write_log


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化（幂等）：create_all 只建缺失的表，再补默认管理员/配置/任务。
    # 空库、半残库、正常库都能安全执行，无需手动跑 init_db.py
    from app.db_init import init_database

    init_database()

    # 补全内置默认配置（含 api.serverUrl），确保已有库也能在配置项页看到
    from app.services.config_service import ensure_default_configs
    from app.services.task_detail_log_service import ensure_table

    ensure_default_configs()
    ensure_table()  # 已有库自动补建任务明细表
    scheduler_service.ensure_default_job_enabled()  # 旧库默认任务改为开启(幂等)
    scheduler_service.start()
    yield
    scheduler_service.shutdown()


app = FastAPI(title=settings.APP_NAME, version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(ApiException, api_exception_handler)


@app.middleware("http")
async def request_log_middleware(request: Request, call_next):
    """记录每一次请求的参数、用户、IP、状态码、耗时与异常原因。"""
    start = time.time()
    params: dict = {}
    body_bytes = b""
    if request.method in ("POST", "PUT", "PATCH"):
        try:
            body_bytes = await request.body()
            payload = json.loads(body_bytes) if body_bytes else {}
            if isinstance(payload, dict):
                for key in ("password", "old_password", "new_password"):
                    if key in payload:
                        payload[key] = "***"
                params = payload
        except Exception:
            params = {"body": body_bytes[:500].decode("utf-8", errors="ignore")}
    params.update(dict(request.query_params))

    response = None
    error_msg = None
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception as exc:
        error_msg = str(exc)
        status_code = 500
        write_log(
            log_type="request", method=request.method, url=str(request.url.path),
            description="请求异常", ip=request.client.host if request.client else None,
            request_params=params, status_code=status_code, success=False,
            error_msg=error_msg, cost_time=int((time.time() - start) * 1000),
        )
        return JSONResponse(status_code=500, content={"code": 500, "msg": "服务器内部错误", "data": None})

    user_name = getattr(request.state, "user_name", "")
    write_log(
        log_type="request", method=request.method, url=str(request.url.path),
        user_name=user_name, ip=request.client.host if request.client else None,
        request_params=params, status_code=status_code,
        success=status_code < 400, error_msg=error_msg,
        cost_time=int((time.time() - start) * 1000),
    )
    return response


# 路由注册
for module in (auth, accounts, feeds, articles, classification, update_log, sys_config, job, logs, open_api):
    app.include_router(module.router, prefix=settings.API_PREFIX)


# 静态资源：文章封面图片 / 公众号封面图片
# 统一从 DATA_DIR（环境变量 DATA_DIR，默认 backend/data）读取，Docker 挂载卷改这个即可
upload_dir = DATA_DIR / "uploadGZHFile"
upload_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploadGZHFile", StaticFiles(directory=str(upload_dir)), name="upload")

cover_dir = DATA_DIR / "uploadGZHCover"
cover_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploadGZHCover", StaticFiles(directory=str(cover_dir)), name="cover")

# 订阅源分类图标
icon_dir = DATA_DIR / "uploadCategoryIcon"
icon_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploadCategoryIcon", StaticFiles(directory=str(icon_dir)), name="category-icon")

# 兼容已有图片路径：源库图片 URL 形如 /profile/uploadGZHCover/xxx，
# 映射到 DATA_DIR 根目录即可直接访问（含正文 HTML 里的 /profile 图片），无需改写已迁移数据
DATA_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/profile", StaticFiles(directory=str(DATA_DIR)), name="profile")


@app.get("/api/health")
def health():
    return ok({"status": "up"})


# 前端静态托管：若存在构建产物 frontend/dist，则由后端一并提供页面。
# 候选路径：本地开发 backend 同级的 frontend/dist；Docker 容器内 /frontend/dist。
# 整段用 try 包裹：前端产物缺失/不完整都只影响页面，绝不让后端 API 启动失败。
_FRONTEND_DIST = next(
    (p for p in (BASE_DIR.parent / "frontend" / "dist", Path("/frontend/dist")) if p.is_dir()),
    None,
)
try:
    if _FRONTEND_DIST and (_FRONTEND_DIST / "index.html").is_file():
        from fastapi.responses import FileResponse

        # 静态资源（js/css/图片等）优先按文件挂载；assets 目录不存在则跳过挂载
        _assets_dir = _FRONTEND_DIST / "assets"
        if _assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa_fallback(full_path: str):
            # API / 文档 / 图片路径不存在时返回 404 JSON，避免被前端兜底吞掉
            if full_path.startswith(("api/", "docs", "openapi.json", "profile/", "upload")):
                return JSONResponse(status_code=404, content={"code": 404, "msg": "not found"})
            # 兜底只服务存在的静态文件，其余返回 index.html（SPA 路由）
            candidate = _FRONTEND_DIST / full_path
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(_FRONTEND_DIST / "index.html")
    else:
        raise RuntimeError("frontend dist not found")
except Exception:
    # 未找到或加载前端产物失败：仅提供后端 API，不影响服务启动
    @app.get("/")
    def root():
        return {"name": settings.APP_NAME, "version": "1.0.0", "docs": "/docs"}
