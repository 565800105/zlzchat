"""对外开放 API（保留原 IndexController 能力，用 key 鉴权）。

包含：订阅源列表、文章列表/详情/正文、Atom RSS 输出、触发同步、订阅源增删/改。
当配置了 api.apiKey 时，请求需携带 key 参数（与原系统一致）。
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any
from urllib.parse import urlparse

import httpx

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.articles import CnvpMpArticles
from app.models.classification import CnvpMpClassification, CnvpMpClassificationDetail
from app.models.feeds import CnvpFeeds
from app.response import ApiException, ok, page_result
from app.services.config_service import get_config, get_config_int, get_public_url
from app.services.crud import paginate, parse_ids
from app.services.wxread import WxReadService

router = APIRouter(prefix="/open", tags=["开放API"])


def _check_key(key: str | None) -> None:
    api_key = get_config("api.apiKey")
    if not api_key:
        raise ApiException("请先设置 api.apiKey 鉴权值", 400)
    if key != api_key:
        raise ApiException("请求 key 不正确", 403)


def _page_params(pageNum: int | None, pageSize: int | None, default_size: int = 20) -> tuple[int, int]:
    """分页参数：未传时用默认值（pageNum=1，pageSize=default_size）。"""
    num = int(pageNum) if pageNum and int(pageNum) > 0 else 1
    size = int(pageSize) if pageSize and int(pageSize) > 0 else default_size
    return num, min(size, 200)


def _camel_to_snake(name: str) -> str:
    """驼峰转下划线：publishTime -> publish_time。"""
    import re

    s = re.sub(r"([A-Z])", r"_\1", name or "")
    return s.strip("_").lower()


def _apply_order(stmt, model, orderByColumn: str | None, isAsc: str | None, default_col: str = "publish_time"):
    """按 orderByColumn/isAsc 安全排序（字段白名单，防 SQL 注入）。

    - orderByColumn 支持驼峰/下划线，逗号分隔多字段（如 publish_time,title）
    - isAsc: asc 升序 / desc 降序（默认 desc）
    - 字段不在模型列中则忽略该字段
    """
    allowed = {c.name for c in model.__table__.columns}
    cols: list[str] = []
    for raw in (orderByColumn or "").split(","):
        name = _camel_to_snake(raw.strip())
        if name in allowed:
            cols.append(name)
    if not cols:
        cols = [default_col if default_col in allowed else next(iter(allowed))]
    asc = str(isAsc or "desc").lower() == "asc"
    for name in cols:
        column = getattr(model, name)
        stmt = stmt.order_by(column.asc() if asc else column.desc())
    return stmt


def _json_page(rows: list, total: int, page_num: int, page_size: int) -> dict:
    """开放 API 的 JSON 分页响应结构。"""
    return ok({"total": total, "pageNum": page_num, "pageSize": page_size, "list": rows})


def _cdata(text: str) -> str:
    """包成安全 CDATA，避免内容里的 ]]> 破坏 XML。"""
    return "<![CDATA[" + (text or "").replace("]]>", "]]]]><![CDATA[>") + "]]>"


def _article_html(article: CnvpMpArticles, public_url: str) -> str:
    """文章正文 HTML：正文/封面图片地址按对外域名补全，并附封面缩略图。"""
    from app.services.config_service import absolute_resource_url

    html = article.content or ""
    # 把正文里的相对图片等资源地址补全为对外可访问地址
    import re

    def repl(match):
        attr, quote, value = match.group(1), match.group(2), match.group(3)
        return f'{attr}={quote}{absolute_resource_url(value, public_url)}{quote}'

    html = re.sub(
        r'(src|href|data-src)\s*=\s*(["\'])(.*?)\2',
        repl,
        html,
        flags=re.IGNORECASE,
    )
    cover = absolute_resource_url(article.pic_url, public_url)
    cover_html = f'<p><img src="{cover}" alt="封面"/></p>' if cover else ""
    return cover_html + html


def _atom_feed(
    title: str,
    articles: list[CnvpMpArticles],
    link_builder,
    logo_url: str | None = None,
    subtitle: str | None = None,
) -> Response:
    public_url = get_public_url()
    updated = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<feed xmlns="http://www.w3.org/2005/Atom">',
        f"<title>{escape(title)}</title>",
    ]
    if subtitle:
        lines.append(f"<subtitle>{escape(subtitle)}</subtitle>")
    lines.append(f"<updated>{updated}</updated>")
    if logo_url:
        from app.services.config_service import absolute_resource_url

        logo = escape(absolute_resource_url(logo_url, public_url), quote=True)
        lines.append(f"<logo>{logo}</logo>")
        lines.append(f"<icon>{logo}</icon>")
    for article in articles:
        pub = article.publish_time.strftime("%Y-%m-%dT%H:%M:%SZ") if article.publish_time else updated
        link = link_builder(article)
        lines.extend([
            "<entry>",
            f"<title>{escape(article.title or '')}</title>",
            f"<id>{escape(article.original_id)}</id>",
            f'<link href="{escape(link, quote=True)}"/>',
            f"<updated>{pub}</updated>",
            f"<summary>{escape((article.content_text or '')[:500])}</summary>",
            f"<content type=\"html\">{_cdata(_article_html(article, public_url))}</content>",
            "</entry>",
        ])
    lines.append("</feed>")
    return Response(content="\n".join(lines), media_type="application/atom+xml; charset=utf-8")


def _rss_feed(
    title: str,
    articles: list[CnvpMpArticles],
    link_builder,
    logo_url: str | None = None,
) -> Response:
    """RSS 2.0 输出（与 Atom 对称，供阅读器订阅）。"""
    from email.utils import format_datetime

    public_url = get_public_url()
    now = datetime.now()
    build_date = format_datetime(now)
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
        "<channel>",
        f"<title>{escape(title)}</title>",
        f"<description>{escape(title)}</description>",
        f"<lastBuildDate>{build_date}</lastBuildDate>",
        f"<pubDate>{build_date}</pubDate>",
        "<language>zh-CN</language>",
    ]
    if logo_url:
        from app.services.config_service import absolute_resource_url

        logo = escape(absolute_resource_url(logo_url, public_url), quote=True)
        lines.append(f"<image><url>{logo}</url><title>{escape(title)}</title></image>")
    for article in articles:
        pub = (
            format_datetime(article.publish_time)
            if article.publish_time
            else build_date
        )
        link = link_builder(article)
        lines.extend([
            "<item>",
            f"<title>{escape(article.title or '')}</title>",
            f"<link>{escape(link, quote=True)}</link>",
            f"<guid isPermaLink=\"false\">{escape(article.original_id or article.articles_id or '')}</guid>",
            f"<pubDate>{pub}</pubDate>",
            f"<description>{_cdata(_article_html(article, public_url))}</description>",
            "</item>",
        ])
    lines.extend(["</channel>", "</rss>"])
    return Response(content="\n".join(lines), media_type="application/rss+xml; charset=utf-8")


@router.get("/feedList")
def feed_list(
    key: str | None = None,
    serarKey: str | None = None,
    searchKey: str | None = None,
    orderByColumn: str | None = None,
    isAsc: str | None = None,
    pageNum: int | None = None,
    pageSize: int | None = None,
    db: Session = Depends(get_db),
):
    """获取当前订阅号列表（支持 serarKey / searchKey 名称模糊搜索）。"""
    _check_key(key)
    from sqlalchemy import select
    from app.models.base import to_dicts

    kw = serarKey or searchKey
    stmt = select(CnvpFeeds).where(CnvpFeeds.is_deleted == 0)
    if kw:
        stmt = stmt.where(CnvpFeeds.mp_name.like(f"%{kw}%"))
    stmt = _apply_order(stmt, CnvpFeeds, orderByColumn, isAsc, default_col="create_time")
    num, size = _page_params(pageNum, pageSize, 20)
    rows, total = paginate(db, stmt, num, size)
    return _json_page(to_dicts(rows), total, num, size)


@router.get("/getArticleList")
def article_list(
    wxsId: str,
    key: str | None = None,
    title: str | None = None,
    pageNum: int = 1,
    pageSize: int = 20,
    db: Session = Depends(get_db),
):
    _check_key(key)
    from sqlalchemy import select

    stmt = select(CnvpMpArticles).where(
        CnvpMpArticles.wxs_id == wxsId, CnvpMpArticles.is_deleted == 0
    )
    if title:
        stmt = stmt.where(CnvpMpArticles.title.like(f"%{title}%"))
    stmt = stmt.order_by(CnvpMpArticles.publish_time.desc())
    rows, total = paginate(db, stmt, pageNum, pageSize)
    from app.models.base import to_dict

    data = [to_dict(row, exclude={"content"}) for row in rows]
    return ok({"total": total, "list": data})


@router.get("/getArticleDetail")
def article_detail(articlesId: str, key: str | None = None, db: Session = Depends(get_db)):
    _check_key(key)
    row = db.get(CnvpMpArticles, articlesId)
    if not row:
        raise ApiException("文章不存在", 404)
    from app.models.base import to_dict

    return ok(to_dict(row))


@router.get("/getArticleText")
def article_text(wxsId: str, key: str | None = None, db: Session = Depends(get_db)):
    _check_key(key)
    rows = (
        db.query(CnvpMpArticles)
        .filter(CnvpMpArticles.wxs_id == wxsId, CnvpMpArticles.is_deleted == 0)
        .order_by(CnvpMpArticles.publish_time.desc())
        .all()
    )
    return ok([{"title": r.title, "text": r.content_text, "picUrls": [r.pic_url] if r.pic_url else []} for r in rows])


# ---------- 对外 JSON 文章列表 ----------
def _article_json_list(
    db: Session,
    base_stmt,
    htmlSta: str | None,
    orderByColumn: str | None,
    isAsc: str | None,
    pageNum: int | None,
    pageSize: int | None,
) -> dict:
    """文章 JSON 列表通用处理：联表带公众号名、排序、分页、按 htmlSta 决定返回正文。

    base_stmt 需为 select(CnvpMpArticles, mp_name, mp_cover) 形式（3 列）。
    """
    from app.models.base import to_dict

    stmt = _apply_order(base_stmt, CnvpMpArticles, orderByColumn, isAsc, default_col="publish_time")
    num, size = _page_params(pageNum, pageSize, 20)
    total = db.query(stmt.subquery()).count()
    rows = db.execute(stmt.offset((num - 1) * size).limit(size)).all()
    keep_html = str(htmlSta or "").strip() in ("1", "true", "True")
    data = []
    for row, mp_name, mp_cover in rows:
        item = to_dict(row)
        item["mpName"] = mp_name or ""
        item["mp_name"] = mp_name or ""
        item["mpCover"] = mp_cover or ""
        item["logo"] = mp_cover or ""
        if not keep_html:
            item["content"] = ""  # htmlSta 为空时不返回正文 HTML
        data.append(item)
    return _json_page(data, total, num, size)


@router.get("/getFeedArticleAllList")
def get_feed_article_all_list(
    key: str | None = None,
    searchKey: str | None = None,
    htmlSta: str | None = None,
    orderByColumn: str | None = None,
    isAsc: str | None = None,
    pageNum: int | None = None,
    pageSize: int | None = None,
    db: Session = Depends(get_db),
):
    """获取全部公众号订阅源 JSON（按标题模糊搜索）。"""
    _check_key(key)
    from sqlalchemy import select

    sub = select(CnvpFeeds.wxs_id, CnvpFeeds.mp_name, CnvpFeeds.mp_cover).subquery()
    stmt = (
        select(CnvpMpArticles, sub.c.mp_name, sub.c.mp_cover)
        .outerjoin(sub, CnvpMpArticles.wxs_id == sub.c.wxs_id)
        .where(CnvpMpArticles.is_deleted == 0)
    )
    if searchKey:
        stmt = stmt.where(CnvpMpArticles.title.like(f"%{searchKey}%"))
    return _article_json_list(db, stmt, htmlSta, orderByColumn, isAsc, pageNum, pageSize)


@router.get("/getFeedArticleList")
def get_feed_article_list(
    wxsId: str,
    key: str | None = None,
    searchKey: str | None = None,
    htmlSta: str | None = None,
    orderByColumn: str | None = None,
    isAsc: str | None = None,
    pageNum: int | None = None,
    pageSize: int | None = None,
    db: Session = Depends(get_db),
):
    """获取指定公众号订阅源 JSON（wxsId + 标题模糊搜索）。"""
    _check_key(key)
    from sqlalchemy import select

    sub = select(CnvpFeeds.wxs_id, CnvpFeeds.mp_name, CnvpFeeds.mp_cover).subquery()
    stmt = (
        select(CnvpMpArticles, sub.c.mp_name, sub.c.mp_cover)
        .outerjoin(sub, CnvpMpArticles.wxs_id == sub.c.wxs_id)
        .where(CnvpMpArticles.wxs_id == wxsId, CnvpMpArticles.is_deleted == 0)
    )
    if searchKey:
        stmt = stmt.where(CnvpMpArticles.title.like(f"%{searchKey}%"))
    return _article_json_list(db, stmt, htmlSta, orderByColumn, isAsc, pageNum, pageSize)


@router.get("/getMpClassification/{classification_id}")
def get_mp_classification(
    classification_id: int,
    key: str | None = None,
    searchKey: str | None = None,
    htmlSta: str | None = None,
    orderByColumn: str | None = None,
    isAsc: str | None = None,
    pageNum: int | None = None,
    pageSize: int | None = None,
    db: Session = Depends(get_db),
):
    """获取分类订阅源 JSON 信息（标题模糊搜索）。"""
    _check_key(key)
    from sqlalchemy import select

    sub = select(CnvpFeeds.wxs_id, CnvpFeeds.mp_name, CnvpFeeds.mp_cover).subquery()
    details = (
        db.query(CnvpMpClassificationDetail.wxs_id)
        .filter(CnvpMpClassificationDetail.classification_id == classification_id)
        .all()
    )
    wxs_ids = [d.wxs_id for d in details if d.wxs_id]
    stmt = (
        select(CnvpMpArticles, sub.c.mp_name, sub.c.mp_cover)
        .outerjoin(sub, CnvpMpArticles.wxs_id == sub.c.wxs_id)
        .where(CnvpMpArticles.is_deleted == 0)
    )
    if wxs_ids:
        stmt = stmt.where(CnvpMpArticles.wxs_id.in_(wxs_ids))
    else:
        stmt = stmt.where(False)  # 分类为空返回空列表
    if searchKey:
        stmt = stmt.where(CnvpMpArticles.title.like(f"%{searchKey}%"))
    return _article_json_list(db, stmt, htmlSta, orderByColumn, isAsc, pageNum, pageSize)


@router.get("/atom")
def atom_all(
    pageNum: int | None = None,
    pageSize: int | None = None,
    orderByColumn: str | None = None,
    isAsc: str | None = None,
    db: Session = Depends(get_db),
):
    from sqlalchemy import select

    num, size = _page_params(pageNum, pageSize, get_config_int("rss.count", 50))
    stmt = select(CnvpMpArticles).where(CnvpMpArticles.is_deleted == 0)
    stmt = _apply_order(stmt, CnvpMpArticles, orderByColumn, isAsc, default_col="publish_time")
    rows = db.scalars(stmt.offset((num - 1) * size).limit(size)).all()
    return _atom_feed(
        get_config("rss.name", "我的订阅"),
        list(rows),
        lambda a: a.links or "",
        subtitle="全部公众号最新文章",
    )


@router.get("/feedAtom/{feed_id}")
def atom_feed(
    feed_id: str,
    pageNum: int | None = None,
    pageSize: int | None = None,
    orderByColumn: str | None = None,
    isAsc: str | None = None,
    db: Session = Depends(get_db),
):
    from sqlalchemy import select

    feed = db.get(CnvpFeeds, feed_id)
    if not feed:
        raise ApiException("公众号不存在", 404)
    default_size = feed.show_count or get_config_int("rss.count", 50)
    num, size = _page_params(pageNum, pageSize, default_size)
    stmt = select(CnvpMpArticles).where(
        CnvpMpArticles.wxs_id == feed.wxs_id, CnvpMpArticles.is_deleted == 0
    )
    stmt = _apply_order(stmt, CnvpMpArticles, orderByColumn, isAsc, default_col="publish_time")
    rows = db.scalars(stmt.offset((num - 1) * size).limit(size)).all()
    return _atom_feed(feed.mp_name, list(rows), lambda a: a.links or "", logo_url=feed.mp_cover)


def _classification_articles(
    classification_id: int,
    db: Session,
    pageNum: int | None = None,
    pageSize: int | None = None,
    orderByColumn: str | None = None,
    isAsc: str | None = None,
):
    """取分类下文章：标题用分类名、条数默认用分类 show_count，返回 (标题, 文章, 图标)。"""
    from sqlalchemy import select

    classification = db.get(CnvpMpClassification, classification_id)
    details = (
        db.query(CnvpMpClassificationDetail)
        .filter(CnvpMpClassificationDetail.classification_id == classification_id)
        .all()
    )
    wxs_ids = [d.wxs_id for d in details if d.wxs_id]
    default_size = (
        classification.show_count
        if classification and classification.show_count
        else get_config_int("rss.count", 50)
    )
    num, size = _page_params(pageNum, pageSize, default_size)
    title = classification.classification_name if classification and classification.classification_name else f"分类 {classification_id}"
    if wxs_ids:
        stmt = select(CnvpMpArticles).where(
            CnvpMpArticles.wxs_id.in_(wxs_ids), CnvpMpArticles.is_deleted == 0
        )
        stmt = _apply_order(stmt, CnvpMpArticles, orderByColumn, isAsc, default_col="publish_time")
        rows = list(db.scalars(stmt.offset((num - 1) * size).limit(size)).all())
    else:
        rows = []
    icon = classification.icon if classification else None
    return title, rows, icon


@router.get("/mpClassificationAtom/{classification_id}")
def atom_classification(
    classification_id: int,
    pageNum: int | None = None,
    pageSize: int | None = None,
    orderByColumn: str | None = None,
    isAsc: str | None = None,
    db: Session = Depends(get_db),
):
    title, rows, icon = _classification_articles(
        classification_id, db, pageNum, pageSize, orderByColumn, isAsc
    )
    return _atom_feed(title, rows, lambda a: a.links or "", logo_url=icon)


@router.get("/mpClassificationRss/{classification_id}")
def rss_classification(
    classification_id: int,
    pageNum: int | None = None,
    pageSize: int | None = None,
    orderByColumn: str | None = None,
    isAsc: str | None = None,
    db: Session = Depends(get_db),
):
    title, rows, icon = _classification_articles(
        classification_id, db, pageNum, pageSize, orderByColumn, isAsc
    )
    return _rss_feed(title, rows, lambda a: a.links or "", logo_url=icon)


@router.get("/rss")
def rss_all(
    pageNum: int | None = None,
    pageSize: int | None = None,
    orderByColumn: str | None = None,
    isAsc: str | None = None,
    db: Session = Depends(get_db),
):
    from sqlalchemy import select

    num, size = _page_params(pageNum, pageSize, get_config_int("rss.count", 50))
    stmt = select(CnvpMpArticles).where(CnvpMpArticles.is_deleted == 0)
    stmt = _apply_order(stmt, CnvpMpArticles, orderByColumn, isAsc, default_col="publish_time")
    rows = list(db.scalars(stmt.offset((num - 1) * size).limit(size)).all())
    return _rss_feed(get_config("rss.name", "我的订阅"), rows, lambda a: a.links or "")


@router.get("/feedRss/{feed_id}")
def rss_feed(
    feed_id: str,
    pageNum: int | None = None,
    pageSize: int | None = None,
    orderByColumn: str | None = None,
    isAsc: str | None = None,
    db: Session = Depends(get_db),
):
    from sqlalchemy import select

    feed = db.get(CnvpFeeds, feed_id)
    if not feed:
        raise ApiException("公众号不存在", 404)
    default_size = feed.show_count or get_config_int("rss.count", 50)
    num, size = _page_params(pageNum, pageSize, default_size)
    stmt = select(CnvpMpArticles).where(
        CnvpMpArticles.wxs_id == feed.wxs_id, CnvpMpArticles.is_deleted == 0
    )
    stmt = _apply_order(stmt, CnvpMpArticles, orderByColumn, isAsc, default_col="publish_time")
    rows = list(db.scalars(stmt.offset((num - 1) * size).limit(size)).all())
    return _rss_feed(feed.mp_name, rows, lambda a: a.links or "", logo_url=feed.mp_cover)


@router.post("/updateFeedAll")
def update_feed_all(key: str | None = None, wxsId: str | None = None, db: Session = Depends(get_db)):
    _check_key(key)
    if wxsId:
        return WxReadService(db).sync_latest(wxsId)
    # 未指定则逐个同步全部自动拉取的公众号
    feeds = db.query(CnvpFeeds).filter(CnvpFeeds.status == 2, CnvpFeeds.is_deleted == 0).all()
    total = 0
    for feed in feeds:
        result = WxReadService(db).sync_latest(feed.wxs_id or "")
        if result.get("code") == 200:
            total += result.get("data", {}).get("updateNum", 0)
    return ok({"updateNum": total})


@router.post("/updateFeed")
def update_feed(wxsId: str, key: str | None = None, db: Session = Depends(get_db)):
    _check_key(key)
    return WxReadService(db).sync_latest(wxsId)


@router.post("/addFeedUrl")
def add_feed_url(linkUrl: str, key: str | None = None, db: Session = Depends(get_db)):
    _check_key(key)
    from app.services.crud import parse_ids
    import uuid

    wxs_id = linkUrl.rstrip("/").split("/")[-1]
    if db.query(CnvpFeeds).filter(CnvpFeeds.wxs_id == wxs_id, CnvpFeeds.is_deleted == 0).first():
        return ok(msg="已存在")
    db.add(CnvpFeeds(
        feed_id=uuid.uuid4().hex, wxs_id=wxs_id, mp_name=wxs_id, mp_cover="", mp_intro="",
        status=2, show_count=20, update_count=0, is_deleted=0,
    ))
    db.commit()
    return ok(msg="添加成功")


@router.post("/addFeedName")
def add_feed_name(feedName: str, key: str | None = None, db: Session = Depends(get_db)):
    _check_key(key)
    import uuid

    db.add(CnvpFeeds(
        feed_id=uuid.uuid4().hex, wxs_id=feedName, mp_name=feedName, mp_cover="", mp_intro="",
        status=2, show_count=20, update_count=0, is_deleted=0,
    ))
    db.commit()
    return ok(msg="添加成功")


@router.post("/removeFeed")
def remove_feed(wxsId: str, key: str | None = None, db: Session = Depends(get_db)):
    """删除订阅源，wxsId 支持逗号分隔多个。"""
    _check_key(key)
    ids = [x.strip() for x in wxsId.split(",") if x.strip()]
    db.query(CnvpFeeds).filter(CnvpFeeds.wxs_id.in_(ids)).update(
        {CnvpFeeds.is_deleted: 1}, synchronize_session=False
    )
    db.commit()
    return ok(msg="删除成功")


@router.post("/updateFeedStatus")
def update_feed_status(wxsId: str, status: int, key: str | None = None, db: Session = Depends(get_db)):
    """公众号切换是否自动拉取，wxsId 支持逗号分隔多个；status：1不拉取 2拉取。"""
    _check_key(key)
    ids = [x.strip() for x in wxsId.split(",") if x.strip()]
    db.query(CnvpFeeds).filter(CnvpFeeds.wxs_id.in_(ids)).update(
        {CnvpFeeds.status: status}, synchronize_session=False
    )
    db.commit()
    return ok(msg="状态已更新")


# ---------- 微信图片代理 ----------
# 微信正文图片(mmbiz.qpic.cn 等)带防盗链：非微信来源 Referer 会返回
# "此图片来自微信公众平台 未经允许不可引用" 占位图。浏览器 <img> 请求无法携带
# 自定义 Referer，因此由后端带微信 Referer 代理转发，前端 img 指向此接口。
_IMAGE_HOSTS = (
    "qpic.cn",      # mmbiz.qpic.cn 等微信图片 CDN
    "qlogo.cn",     # mmbiz.qlogo.cn 头像
    "gtimg.com",    # 微信部分静态资源
    "qq.com",       # res.wx.qq.com 等
)
_WX_IMAGE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    ),
    "Referer": "https://mp.weixin.qq.com/",
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
}


def _is_allowed_image_url(url: str) -> bool:
    """仅允许微信系图片域名，防止被用于 SSRF 探测内网。"""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        host = (parsed.hostname or "").lower()
        return any(host == h or host.endswith("." + h) for h in _IMAGE_HOSTS)
    except Exception:
        return False


@router.get("/image-proxy")
def image_proxy(url: str):
    """带微信 Referer 代理图片，绕过防盗链；仅允许微信图片域名。"""
    if not url or not _is_allowed_image_url(url):
        raise ApiException("非法的图片地址", 403)
    try:
        resp = httpx.get(url, headers=_WX_IMAGE_HEADERS, timeout=20, follow_redirects=True)
        content_type = resp.headers.get("content-type", "image/jpeg")
        # 微信有时返回占位图 HTML，检测并回传明确错误，前端可显示占位
        if "text/html" in content_type:
            raise ApiException("图片来源拒绝访问", 403)
        return Response(
            content=resp.content,
            media_type=content_type,
            headers={"Cache-Control": "public, max-age=86400"},
        )
    except ApiException:
        raise
    except Exception as exc:
        raise ApiException(f"图片代理失败: {exc}", 502)
