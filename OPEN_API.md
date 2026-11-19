# zlzchat 对外开放 API 文档

对外接口统一前缀：`/api/open`，服务地址例如 `http://服务器对外域名:8100`。
供外部程序获取订阅数据、触发同步、管理公众号。

---

## 一、鉴权

除公开的 Atom/RSS 订阅源接口（见下方无需 key 清单）外，其余接口都需要 `key` 参数鉴权：

1. 在后台「系统 → 配置项」中设置 `api.apiKey` 的值（服务提供 api 鉴权 key）。
2. 每个请求带上 `key=<你设置的 apiKey>`。

> - **未设置 `api.apiKey` 时调用需鉴权接口会返回错误**：`{"code": 400, "msg": "请先设置 api.apiKey 鉴权值"}`。请先在后台「系统 → 配置项」设置该项。
> - 已设置但 key 不正确时返回 `{"code": 403, "msg": "请求 key 不正确"}`。
> - 以下接口**无需 key**（公开订阅源）：`/atom`、`/rss`、`/feedAtom/{feedId}`、`/feedRss/{feedId}`、`/mpClassificationAtom/{classificationId}`、`/mpClassificationRss/{classificationId}`。

---

## 二、通用参数

| 参数 | 说明 |
| --- | --- |
| `key` | 鉴权 key（见上），公开订阅源接口不需要 |
| `pageNum` | 第几页，默认 `1` |
| `pageSize` | 每页条数，默认 `20`（Atom/RSS 默认取配置项 `rss.count` 或公众号/分类的显示条数）；最大 200 |
| `orderByColumn` | 排序字段，数据库下划线命名，支持驼峰（如 `publishTime`）、支持逗号分隔多字段；如 `publish_time`、`create_time`、`title` |
| `isAsc` | `asc` 升序 / `desc` 降序，默认 `desc` |
| `searchKey` | 文章标题模糊搜索（`%searchKey%`）；`feedList` 接口的名称搜索参数为 `serarKey` |
| `htmlSta` | 仅 JSON 文章列表接口：`1` 返回正文 HTML `content`，不传或空则 `content` 返回空串 |

**成功响应结构**（JSON 接口）：

```json
{
  "code": 200,
  "msg": "ok",
  "data": {
    "total": 42,
    "pageNum": 1,
    "pageSize": 20,
    "list": [ { "...": "文章/公众号字段" } ]
  }
}
```

> 标识：`code=200` 为成功。字段 `logo`/`mpCover` 为公众号封面，`mp_name`/`mpName` 为公众号名称。

**失败响应**：`{"code": 403, "msg": "请求 key 不正确", "data": null}`。

---

## 三、接口清单

### 1. 订阅源类（XML，无需 key）

#### 1.1 获取全部公众号 Atom 订阅源
```
GET /api/open/atom?pageNum=1&pageSize=20&orderByColumn=publish_time&isAsc=desc
```
分页默认取配置 `rss.count`。响应 `Content-Type: application/atom+xml; charset=utf-8`。

#### 1.2 获取全部公众号 RSS 订阅源
```
GET /api/open/rss?pageNum=1&pageSize=20&orderByColumn=publish_time&isAsc=desc
```

#### 1.3 获取某个公众号 Atom 订阅源
```
GET /api/open/feedAtom/{feedId}?pageNum=1&pageSize=20&orderByColumn=publish_time&isAsc=desc
```
`feedId`：后台「公众号」菜单里公众号的 ID。分页默认取该公众号「显示条数」。

#### 1.4 获取某个公众号 RSS 订阅源
```
GET /api/open/feedRss/{feedId}?pageNum=1&pageSize=20
```

#### 1.5 获取分类 Atom 订阅源
```
GET /api/open/mpClassificationAtom/{classificationId}?pageNum=1&pageSize=20&orderByColumn=publish_time&isAsc=desc
```
`classificationId`：后台「订阅源分类」里分类的 ID。分页默认取该分类「显示条数」。

#### 1.6 获取分类 RSS 订阅源
```
GET /api/open/mpClassificationRss/{classificationId}?pageNum=1&pageSize=20
```

> 订阅源中图片资源前缀取自配置项 `api.publicUrl`（服务器对外域名/IP），未配置时用相对路径。

---

### 2. 数据查询类（JSON，需要 key）

#### 2.1 获取全部公众号订阅源 JSON
```
GET /api/open/getFeedArticleAllList?key=KEY&searchKey=&pageNum=1&pageSize=20&orderByColumn=publish_time&isAsc=desc&htmlSta=
```
- `searchKey`：搜索文章标题，模糊查询。

#### 2.2 获取指定公众号订阅源 JSON
```
GET /api/open/getFeedArticleList?key=KEY&wxsId=MP_WXS_xxx&searchKey=&pageNum=1&pageSize=20&orderByColumn=publish_time&isAsc=desc&htmlSta=
```
- `wxsId`：后台获取（公众号的微信读书 ID）。
- `searchKey`：搜索文章标题，模糊查询。

#### 2.3 获取分类订阅源 JSON
```
GET /api/open/getMpClassification/{classificationId}?key=KEY&searchKey=&pageNum=1&pageSize=20&orderByColumn=publish_time&isAsc=desc&htmlSta=
```
- `classificationId`：后台订阅源分类获取。
- `searchKey`：搜索文章标题，模糊查询。

#### 2.4 获取当前订阅号列表
```
GET /api/open/feedList?key=KEY&serarKey=&orderByColumn=create_time&isAsc=desc&pageNum=1&pageSize=20
```
- `serarKey`：按公众号名称模糊搜索（也接受 `searchKey`）。

---

### 3. 操作类（需要 key）

#### 3.1 执行公众号更新任务（全部）
```
GET|POST /api/open/updateFeedAll?key=KEY
```
触发全部「自动拉取」公众号的更新任务。

#### 3.2 指定某个公众号更新任务
```
GET|POST /api/open/updateFeed?key=KEY&wxsId=MP_WXS_xxx
```

#### 3.3 根据名称添加公众号
```
GET|POST /api/open/addFeedName?key=KEY&feedName=公众号名称
```

#### 3.4 根据文章地址添加公众号
```
GET|POST /api/open/addFeedUrl?key=KEY&linkUrl=文章地址
```

#### 3.5 删除订阅源
```
GET|POST /api/open/removeFeed?key=KEY&wxsId=MP_WXS_2392048137,MP_WXS_3915508834
```
`wxsId` 逗号隔开可多个（逻辑删除）。

#### 3.6 公众号切换是否自动拉取
```
GET|POST /api/open/updateFeedStatus?key=KEY&wxsId=MP_WXS_xxx,MP_WXS_yyy&status=2
```
- `status`：`1` 不拉取（只能手动拉取，定时任务不会拉取）、`2` 拉取。
- `wxsId` 逗号隔开可多个。

---

## 四、调用示例

```bash
# 1. 设置 api.apiKey 后，获取全部文章 JSON（按发布时间倒序，第一页 20 条）
curl "http://your-host:8100/api/open/getFeedArticleAllList?key=YOUR_KEY&pageNum=1&pageSize=20&orderByColumn=publish_time&isAsc=desc"

# 2. 搜索标题含"咖啡"的文章
curl "http://your-host:8100/api/open/getFeedArticleAllList?key=YOUR_KEY&searchKey=咖啡"

# 3. 获取全部公众号 Atom 订阅源（无需 key）
curl "http://your-host:8100/api/open/atom?pageNum=1&pageSize=20"

# 4. 触发全部公众号更新
curl "http://your-host:8100/api/open/updateFeedAll?key=YOUR_KEY"

# 5. 批量关闭自动拉取
curl "http://your-host:8100/api/open/updateFeedStatus?key=YOUR_KEY&wxsId=MP_WXS_111,MP_WXS_222&status=1"
```

---

## 五、其他可用接口

以下接口仍可用，新接入建议使用上面的标准接口：

- `/api/open/getArticleList?key=&wxsId=&title=&pageNum=&pageSize=`
- `/api/open/getArticleDetail?key=&articlesId=`
- `/api/open/getArticleText?key=&wxsId=`
- `/api/open/image-proxy?url=`（微信图片代理，见正文图片防盗链说明）
