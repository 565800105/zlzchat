"""公众号信息接口 /api/admin/feeds。"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models.articles import CnvpMpArticles
from app.models.base import to_dict, to_dicts
from app.models.classification import CnvpMpClassificationDetail
from app.models.feeds import CnvpFeeds
from app.models.user import SysUser
from app.response import ApiException, ok, page_result
from app.services.crud import get_val, apply_audit, fill, paginate, parse_ids
from app.services.log_service import write_log

router = APIRouter(prefix="/admin/feeds", tags=["公众号信息"])

_FIELDS = ["wxs_id", "mp_name", "mp_cover", "mp_intro", "status", "show_count", "update_count", "version", "is_deleted"]


def _feed_dict(row: CnvpFeeds, article_num: int | None = None) -> dict[str, Any]:
    data = to_dict(row, exclude={"remark"})
    data["version"] = row.version or ""
    if article_num is not None:
        data["articleNum"] = article_num
    return data


@router.get("/list")
def list_feeds(
    pageNum: int = Query(1, ge=1),
    pageSize: int = Query(10, ge=1),
    mpName: str | None = None,
    wxsId: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    # 联表统计文章数
    sub = (
        select(CnvpMpArticles.wxs_id, func.count().label("article_num"))
        .where(CnvpMpArticles.is_deleted == 0)
        .group_by(CnvpMpArticles.wxs_id)
        .subquery()
    )
    stmt = (
        select(CnvpFeeds, func.coalesce(sub.c.article_num, 0).label("cnt"))
        .outerjoin(sub, CnvpFeeds.wxs_id == sub.c.wxs_id)
        .where(CnvpFeeds.is_deleted == 0)
    )
    if mpName:
        stmt = stmt.where(CnvpFeeds.mp_name.like(f"%{mpName}%"))
    if wxsId:
        stmt = stmt.where(CnvpFeeds.wxs_id == wxsId)
    # status 允许传空字符串（前端筛选项清空时），空串/非法值均视为不筛选
    status_value = None
    if status is not None and str(status).strip() != "":
        try:
            status_value = int(status)
        except (TypeError, ValueError):
            status_value = None
    if status_value is not None:
        stmt = stmt.where(CnvpFeeds.status == status_value)
    stmt = stmt.order_by(CnvpFeeds.create_time.desc())

    total = db.query(stmt.subquery()).count()
    rows = db.execute(stmt.offset((pageNum - 1) * pageSize).limit(pageSize)).all()
    data = [_feed_dict(row, int(cnt or 0)) for row, cnt in rows]
    return page_result(data, total, pageNum, pageSize)


@router.get("/all")
def all_feeds(db: Session = Depends(get_db), _: SysUser = Depends(get_current_user)):
    """下拉/左侧列表用：返回全部未删除公众号（含文章数、封面）。"""
    sub = (
        select(CnvpMpArticles.wxs_id, func.count().label("article_num"))
        .where(CnvpMpArticles.is_deleted == 0)
        .group_by(CnvpMpArticles.wxs_id)
        .subquery()
    )
    rows = (
        db.query(CnvpFeeds, func.coalesce(sub.c.article_num, 0).label("cnt"))
        .outerjoin(sub, CnvpFeeds.wxs_id == sub.c.wxs_id)
        .filter(CnvpFeeds.is_deleted == 0)
        .order_by(CnvpFeeds.mp_name)
        .all()
    )
    return ok([_feed_dict(row, int(cnt or 0)) for row, cnt in rows])


@router.post("/add")
def add_feed(
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    if not get_val(payload, "mp_name"):
        raise ApiException("公众号名称不能为空")
    row = CnvpFeeds(
        feed_id=get_val(payload, "feed_id") or uuid.uuid4().hex,
        mp_cover="",
        mp_intro="",
        status=2,
        show_count=20,
        update_count=0,
        is_deleted=0,
    )
    fill(row, payload, _FIELDS)
    apply_audit(row, user.user_name, True)
    db.add(row)
    db.commit()
    write_log(log_type="operation", method="POST", url=str(request.url.path), description="新增公众号", user_name=user.user_name, request_params=payload)
    return ok(msg="新增成功")


@router.get("/searchFeed")
def search_feed(
    feedName: str = Query("", description="公众号名称"),
    db: Session = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    """按名称搜索微信读书公众号（对应 Java searchFeed）。"""
    from app.services.wxread import WxReadService, AccountError

    try:
        books = WxReadService(db).search_feed(feedName)
    except AccountError as exc:
        raise ApiException(str(exc), 400)
    return ok(books, msg="获取成功")


@router.post("/addFeed")
def add_feed_from_book(
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    """从微信读书搜索结果（bookInfo）添加订阅源（对应 Java addFeed）。"""
    from app.services.wxread import WxReadService, AccountError

    try:
        result = WxReadService(db).add_feed_from_search(payload)
    except AccountError as exc:
        raise ApiException(str(exc), 400)
    write_log(log_type="operation", method="POST", url=str(request.url.path), description="搜索添加公众号", user_name=user.user_name, request_params=payload)
    return ok(result, msg="添加成功")


@router.post("/addLinkFeed")
def add_feed_from_link(
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    """根据文章链接解析并添加订阅源（对应 Java addLinkFeed）。"""
    from app.services.wxread import WxReadService, AccountError

    link_url = str(get_val(payload, "linkUrl", ""))
    try:
        result = WxReadService(db).add_feed_from_link(link_url)
    except AccountError as exc:
        raise ApiException(str(exc), 400)
    write_log(log_type="operation", method="POST", url=str(request.url.path), description="链接添加公众号", user_name=user.user_name, request_params=payload)
    return ok(result, msg="添加成功")


@router.get("/feedTreeData")
def feed_tree_data(db: Session = Depends(get_db), _: SysUser = Depends(get_current_user)):
    """树形数据：wxs_id 作为节点 id。"""
    rows = db.query(CnvpFeeds).filter(CnvpFeeds.is_deleted == 0).all()
    return ok([{"id": row.wxs_id, "pId": 0, "name": row.mp_name, "open": True} for row in rows])


@router.get("/download-opml")
def download_opml(request: Request, db: Session = Depends(get_db), _: SysUser = Depends(get_current_user)):
    """导出 OPML 订阅列表（对应 Java downloadOpml，文件名 zlzchat.opml）。

    域名优先取配置项 api.publicUrl（服务器对外域名/IP），否则回退 baseUrl 查询参数 / 请求地址。
    """
    from xml.sax.saxutils import quoteattr

    from fastapi.responses import Response

    from app.services.config_service import get_public_url

    rows = db.query(CnvpFeeds).filter(CnvpFeeds.is_deleted == 0).all()
    base = (
        get_public_url()
        or request.query_params.get("baseUrl")
        or str(request.base_url)
    ).rstrip("/")
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<opml version="2.0"><head><title>zlzchat订阅列表</title></head><body>',
    ]
    for row in rows:
        link = f"{base}/api/open/feedAtom/{row.feed_id}"
        lines.append(
            f"<outline text={quoteattr(row.mp_name or '')} title={quoteattr(row.mp_name or '')} "
            f'type="rss" xmlUrl={quoteattr(link)} htmlUrl={quoteattr(link)}/>'
        )
    lines.append("</body></opml>")
    return Response(
        content="\n".join(lines).encode("utf-8"),
        media_type="application/xml; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="zlzchat.opml"'},
    )


@router.post("/edit")
def edit_feed(
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    feed_id = get_val(payload, "feed_id")
    row = db.get(CnvpFeeds, feed_id) if feed_id else None
    if not row:
        raise ApiException("记录不存在", 404)
    fill(row, payload, _FIELDS)
    apply_audit(row, user.user_name, False)
    db.commit()
    write_log(log_type="operation", method="POST", url=str(request.url.path), description="编辑公众号", user_name=user.user_name, request_params=payload)
    return ok(msg="修改成功")


@router.post("/remove")
def remove_feeds(
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    ids = parse_ids(get_val(payload, "ids"))
    if not ids:
        raise ApiException("未选择记录")
    db.query(CnvpFeeds).filter(CnvpFeeds.feed_id.in_(ids)).update({CnvpFeeds.is_deleted: 1}, synchronize_session=False)
    db.commit()
    write_log(log_type="operation", method="POST", url=str(request.url.path), description="删除公众号", user_name=user.user_name, request_params=payload)
    return ok(msg="删除成功")


@router.get("/{feed_id}")
def get_feed(feed_id: str, db: Session = Depends(get_db), _: SysUser = Depends(get_current_user)):
    row = db.get(CnvpFeeds, feed_id)
    if not row:
        raise ApiException("记录不存在", 404)
    return ok(_feed_dict(row))
