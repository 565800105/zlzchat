"""订阅源分类接口 /api/admin/classification 及其明细。"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import DATA_DIR
from app.database import get_db
from app.deps import get_current_user
from app.models.base import to_dict, to_dicts
from app.models.classification import CnvpMpClassification, CnvpMpClassificationDetail
from app.models.feeds import CnvpFeeds
from app.models.user import SysUser
from app.response import ApiException, ok, page_result
from app.services.crud import get_val, apply_audit, fill, paginate, parse_ids
from app.services.log_service import write_log

router = APIRouter(prefix="/admin/classification", tags=["订阅源分类"])

_FIELDS = ["classification_name", "show_count", "icon", "is_deleted", "remark"]
_DETAIL_FIELDS = ["feed_id", "mp_name", "mp_cover", "wxs_id", "classification_id", "remark"]

# 分类图标独立目录，访问路径 /uploadCategoryIcon
ICON_DIR = DATA_DIR / "uploadCategoryIcon"
ICON_URL_PREFIX = "/uploadCategoryIcon"
_ALLOWED_ICON_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico"}
_MAX_ICON_BYTES = 5 * 1024 * 1024  # 5MB


@router.post("/upload-icon")
async def upload_icon(
    file: UploadFile = File(..., description="分类图标图片"),
    _: SysUser = Depends(get_current_user),
):
    """上传分类图标，保存到独立目录，返回可访问 URL。"""
    original = file.filename or ""
    ext = Path(original).suffix.lower()
    if ext not in _ALLOWED_ICON_EXTS:
        raise ApiException(f"仅支持图片格式：{', '.join(sorted(_ALLOWED_ICON_EXTS))}")
    content = await file.read()
    if not content:
        raise ApiException("文件内容为空")
    if len(content) > _MAX_ICON_BYTES:
        raise ApiException("图片大小不能超过 5MB")
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    (ICON_DIR / filename).write_bytes(content)
    return ok({"url": f"{ICON_URL_PREFIX}/{filename}", "filename": filename})


# ---------- 分类主表 ----------
@router.get("/list")
def list_classification(
    pageNum: int = Query(1, ge=1),
    pageSize: int = Query(10, ge=1),
    classificationName: str | None = None,
    db: Session = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    stmt = select(CnvpMpClassification).where(CnvpMpClassification.is_deleted == 0)
    if classificationName:
        stmt = stmt.where(CnvpMpClassification.classification_name.like(f"%{classificationName}%"))
    stmt = stmt.order_by(CnvpMpClassification.create_time.desc())
    rows, total = paginate(db, stmt, pageNum, pageSize)
    data = to_dicts(rows)

    # 批量统计每个分类下的公众号(明细)个数，避免逐行查询
    if rows:
        ids = [row.classification_id for row in rows]
        counts = dict(
            db.query(
                CnvpMpClassificationDetail.classification_id,
                func.count(CnvpMpClassificationDetail.classification_detai_id),
            )
            .filter(CnvpMpClassificationDetail.classification_id.in_(ids))
            .group_by(CnvpMpClassificationDetail.classification_id)
            .all()
        )
        for item in data:
            cid = item.get("classification_id")
            item["feedCount"] = int(counts.get(cid, 0))
    return page_result(data, total, pageNum, pageSize)


@router.get("/options")
def classification_options(db: Session = Depends(get_db), _: SysUser = Depends(get_current_user)):
    """定时任务选择器用：返回全部分类。"""
    rows = db.query(CnvpMpClassification).filter(CnvpMpClassification.is_deleted == 0).all()
    return ok(to_dicts(rows))


@router.post("/add")
def add_classification(
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    row = CnvpMpClassification(show_count=20, is_deleted=0)
    fill(row, payload, _FIELDS)
    apply_audit(row, user.user_name, True)
    db.add(row)
    db.commit()
    write_log(log_type="operation", method="POST", url=str(request.url.path), description="新增分类", user_name=user.user_name, request_params=payload)
    return ok(msg="新增成功")


@router.post("/edit")
def edit_classification(
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    row = db.get(CnvpMpClassification, get_val(payload, "classification_id")) if get_val(payload, "classification_id") else None
    if not row:
        raise ApiException("记录不存在", 404)
    fill(row, payload, _FIELDS)
    apply_audit(row, user.user_name, False)
    db.commit()
    write_log(log_type="operation", method="POST", url=str(request.url.path), description="编辑分类", user_name=user.user_name, request_params=payload)
    return ok(msg="修改成功")


@router.post("/remove")
def remove_classification(
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    ids = parse_ids(get_val(payload, "ids"))
    if not ids:
        raise ApiException("未选择记录")
    db.query(CnvpMpClassification).filter(CnvpMpClassification.classification_id.in_(ids)).update(
        {CnvpMpClassification.is_deleted: 1}, synchronize_session=False
    )
    db.commit()
    write_log(log_type="operation", method="POST", url=str(request.url.path), description="删除分类", user_name=user.user_name, request_params=payload)
    return ok(msg="删除成功")


@router.get("/download-opml")
def download_opml(
    request: Request,
    rssType: str = "atom",
    db: Session = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    """导出 OPML：每个分类一个 outline，订阅地址指向对应格式的分类订阅源。

    rssType=atom 用 /api/open/mpClassificationAtom/{id}，rss 用 .../mpClassificationRss/{id}。
    域名优先取配置项 api.publicUrl（服务器对外域名/IP），否则回退查询参数 baseUrl / 请求 base_url。
    """
    from fastapi.responses import Response
    from html import escape

    from app.services.config_service import get_config, get_public_url

    base = (
        get_public_url()
        or request.query_params.get("baseUrl")
        or str(request.base_url)
    ).rstrip("/")
    rss_type = "rss" if (rssType or "").lower() == "rss" else "atom"
    endpoint = "mpClassificationRss" if rss_type == "rss" else "mpClassificationAtom"
    all_endpoint = "rss" if rss_type == "rss" else "atom"

    rows = (
        db.query(CnvpMpClassification)
        .filter(CnvpMpClassification.is_deleted == 0)
        .order_by(CnvpMpClassification.create_time.desc())
        .all()
    )
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<opml version="2.0">',
        "<head><title>zlzchat订阅分类列表</title></head>",
        "<body>",
    ]
    # 全部公众号最新文章订阅地址（用 rss.name 标题、rss.count 条数）
    all_name = escape(get_config("rss.name", "我的订阅") or "全部公众号最新文章")
    all_url = escape(f"{base}/api/open/{all_endpoint}", quote=True)
    lines.append(
        f'<outline text="{all_name}" title="{all_name}" type="rss" '
        f'xmlUrl="{all_url}" htmlUrl="{all_url}"/>'
    )
    for row in rows:
        name = escape(row.classification_name or "")
        url = escape(f"{base}/api/open/{endpoint}/{row.classification_id}", quote=True)
        lines.append(
            f'<outline text="{name}" title="{name}" type="rss" '
            f'xmlUrl="{url}" htmlUrl="{url}"/>'
        )
    lines.extend(["</body>", "</opml>"])
    return Response(
        content="\n".join(lines),
        media_type="application/xml; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="zlzchatcategory.opml"'},
    )


# ---------- 分类明细 ----------
@router.get("/detail/list")
def list_detail(
    classificationId: int = Query(...),
    db: Session = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    rows = (
        db.query(CnvpMpClassificationDetail)
        .filter(CnvpMpClassificationDetail.classification_id == classificationId)
        .order_by(CnvpMpClassificationDetail.create_time.desc())
        .all()
    )
    return ok(to_dicts(rows))


@router.post("/detail/add")
def add_detail(
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    """批量添加明细：remark 为逗号分隔的 wxs_id，查 feeds 生成明细并去重。"""
    classification_id = int(get_val(payload, "classification_id") or 0)
    if not classification_id:
        raise ApiException("缺少 classification_id")
    wxs_ids = [x.strip() for x in str(get_val(payload, "remark", "")).split(",") if x.strip()]
    if not wxs_ids:
        raise ApiException("请填写要添加的公众号 wxs_id（逗号分隔）")

    feeds = (
        db.query(CnvpFeeds)
        .filter(CnvpFeeds.wxs_id.in_(wxs_ids), CnvpFeeds.is_deleted == 0)
        .all()
    )
    for feed in feeds:
        exists = (
            db.query(CnvpMpClassificationDetail)
            .filter(
                CnvpMpClassificationDetail.classification_id == classification_id,
                CnvpMpClassificationDetail.wxs_id == feed.wxs_id,
            )
            .first()
        )
        if exists:
            continue
        row = CnvpMpClassificationDetail(
            feed_id=feed.feed_id,
            mp_name=feed.mp_name,
            mp_cover=feed.mp_cover,
            wxs_id=feed.wxs_id,
            classification_id=classification_id,
        )
        apply_audit(row, user.user_name, True)
        db.add(row)
    db.commit()
    write_log(log_type="operation", method="POST", url=str(request.url.path), description="批量添加分类明细", user_name=user.user_name, request_params=payload)
    return ok(msg="添加成功")


@router.post("/detail/edit")
def edit_detail(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    row = db.get(CnvpMpClassificationDetail, get_val(payload, "classification_detai_id")) if get_val(payload, "classification_detai_id") else None
    if not row:
        raise ApiException("记录不存在", 404)
    fill(row, payload, _DETAIL_FIELDS)
    apply_audit(row, user.user_name, False)
    db.commit()
    return ok(msg="修改成功")


@router.post("/detail/remove")
def remove_detail(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    ids = parse_ids(get_val(payload, "ids"))
    if not ids:
        raise ApiException("未选择记录")
    db.query(CnvpMpClassificationDetail).filter(
        CnvpMpClassificationDetail.classification_detai_id.in_(ids)
    ).delete(synchronize_session=False)
    db.commit()
    return ok(msg="删除成功")


@router.get("/{classification_id}")
def get_classification(classification_id: int, db: Session = Depends(get_db), _: SysUser = Depends(get_current_user)):
    row = db.get(CnvpMpClassification, classification_id)
    if not row:
        raise ApiException("记录不存在", 404)
    return ok(to_dict(row))
