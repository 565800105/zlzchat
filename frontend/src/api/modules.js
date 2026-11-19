import request from './request'

/**
 * 所有业务 API 集中于此，页面不直接散落 axios 调用。
 * 每个函数 resolve 的是后端统一响应的 data 字段。
 */
const unwrap = (promise) => promise.then((res) => res.data)

/* ============================ 鉴权 auth ============================ */
export const authApi = {
  login: (data) => unwrap(request.post('/auth/login', data)),
  info: () => unwrap(request.get('/auth/info')),
  logout: () => unwrap(request.post('/auth/logout')),
  changePassword: (data) => unwrap(request.post('/auth/password', data)),
}

/* ========================== 账号配置 accounts ======================== */
export const accountsApi = {
  list: (params) => unwrap(request.get('/admin/accounts/list', { params })),
  get: (id) => unwrap(request.get(`/admin/accounts/${id}`)),
  add: (data) => unwrap(request.post('/admin/accounts/add', data)),
  edit: (data) => unwrap(request.post('/admin/accounts/edit', data)),
  remove: (ids) => unwrap(request.post('/admin/accounts/remove', { ids })),
  // 微信读书扫码登录
  qrcode: () => unwrap(request.get('/admin/accounts/qrcode')),
  qrcodeCheck: (uid, installId) =>
    unwrap(request.get('/admin/accounts/qrcode/check', { params: { uid, installId } })),
}

/* ========================== 公众号信息 feeds ======================== */
export const feedsApi = {
  list: (params) => unwrap(request.get('/admin/feeds/list', { params })),
  all: () => unwrap(request.get('/admin/feeds/all')),
  get: (id) => unwrap(request.get(`/admin/feeds/${id}`)),
  add: (data) => unwrap(request.post('/admin/feeds/add', data)),
  edit: (data) => unwrap(request.post('/admin/feeds/edit', data)),
  remove: (ids) => unwrap(request.post('/admin/feeds/remove', { ids })),
  // 原系统三种添加方式：名称搜索、链接解析、OPML 导出
  searchFeed: (feedName) =>
    unwrap(request.get('/admin/feeds/searchFeed', { params: { feedName } })),
  addFeed: (bookInfo) => unwrap(request.post('/admin/feeds/addFeed', bookInfo)),
  addLinkFeed: (linkUrl) => unwrap(request.post('/admin/feeds/addLinkFeed', { linkUrl })),
  // 文件下载：响应为二进制流，不经 unwrap 解包
  downloadOpml: () =>
    request.get('/admin/feeds/download-opml', {
      params: { baseUrl: window.location.origin },
      responseType: 'blob',
    }),
}

/* ========================== 文章信息 mparticles ===================== */
export const articlesApi = {
  list: (params) => unwrap(request.get('/admin/mparticles/list', { params })),
  get: (id) => unwrap(request.get(`/admin/mparticles/${id}`)),
  add: (data) => unwrap(request.post('/admin/mparticles/add', data)),
  edit: (data) => unwrap(request.post('/admin/mparticles/edit', data)),
  remove: (ids) => unwrap(request.post('/admin/mparticles/remove', { ids })),
  // 重新抓取正文
  reFetch: (id) => unwrap(request.post(`/admin/mparticles/goCont/${id}`)),
  // 同步最新文章
  syncLatest: (wxsId, taskId) =>
    unwrap(request.post(`/admin/mparticles/getFeedArticleNew/${wxsId}`, null, { params: taskId ? { taskId } : {} })),
  // 同步历史文章
  syncHistory: (wxsId, data) => unwrap(request.post(`/admin/mparticles/getFeedArticle/${wxsId}`, data)),
  // 刷新后查询后台任务真实状态
  taskStatus: (taskId) => unwrap(request.get(`/admin/mparticles/taskStatus/${taskId}`)),
  // 清空公众号文章
  clearFeedArticles: (wxsId) => unwrap(request.post(`/admin/mparticles/deleteFeedArticle/${wxsId}`)),
}

/* ====================== 订阅源分类 classification =================== */
export const classificationApi = {
  list: (params) => unwrap(request.get('/admin/classification/list', { params })),
  options: () => unwrap(request.get('/admin/classification/options')),
  get: (id) => unwrap(request.get(`/admin/classification/${id}`)),
  add: (data) => unwrap(request.post('/admin/classification/add', data)),
  edit: (data) => unwrap(request.post('/admin/classification/edit', data)),
  remove: (ids) => unwrap(request.post('/admin/classification/remove', { ids })),
  // 分类明细
  detailList: (classificationId) =>
    unwrap(request.get('/admin/classification/detail/list', { params: { classificationId } })),
  detailAdd: (data) => unwrap(request.post('/admin/classification/detail/add', data)),
  detailEdit: (data) => unwrap(request.post('/admin/classification/detail/edit', data)),
  detailRemove: (ids) => unwrap(request.post('/admin/classification/detail/remove', { ids })),
  // 分类图标上传：FormData，返回 { url, filename }
  uploadIcon: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    // 不手动设置 Content-Type，交由 axios/浏览器自动附加 multipart boundary
    return unwrap(request.post('/admin/classification/upload-icon', formData))
  },
  // 导出分类订阅源 OPML（二进制流，不经 unwrap）
  downloadOpml: (rssType) =>
    request.get('/admin/classification/download-opml', {
      params: { rssType, baseUrl: window.location.origin },
      responseType: 'blob',
    }),
}

/* ======================== 更新记录 updateLog ======================== */
export const updateLogApi = {
  list: (params) => unwrap(request.get('/admin/updateLog/list', { params })),
  get: (id) => unwrap(request.get(`/admin/updateLog/${id}`)),
  add: (data) => unwrap(request.post('/admin/updateLog/add', data)),
  edit: (data) => unwrap(request.post('/admin/updateLog/edit', data)),
  remove: (ids) => unwrap(request.post('/admin/updateLog/remove', { ids })),
}

/* ========================== 配置项 config =========================== */
export const configApi = {
  list: () => unwrap(request.get('/admin/config/list')),
  edit: (data) => unwrap(request.post('/admin/config/edit', data)),
  batch: (values) => unwrap(request.post('/admin/config/batch', { values })),
}

/* ========================== 定时任务 job ============================ */
export const jobApi = {
  list: (params) => unwrap(request.get('/admin/job/list', { params })),
  get: (id) => unwrap(request.get(`/admin/job/${id}`)),
  classificationOptions: () => unwrap(request.get('/admin/job/classification-options')),
  feedOptions: () => unwrap(request.get('/admin/job/feed-options')),
  add: (data) => unwrap(request.post('/admin/job/add', data)),
  edit: (data) => unwrap(request.post('/admin/job/edit', data)),
  remove: (ids) => unwrap(request.post('/admin/job/remove', { ids })),
  run: (jobId) => unwrap(request.post(`/admin/job/run/${jobId}`)),
  toggle: (jobId) => unwrap(request.post(`/admin/job/toggle/${jobId}`)),
}

/* ============================ 日志 logs ============================= */
export const logsApi = {
  list: (params) => unwrap(request.get('/admin/logs/list', { params })),
  stats: () => unwrap(request.get('/admin/logs/stats')),
  // 任务明细日志（文本框展示，按批次回溯）
  detailList: (params) => unwrap(request.get('/admin/logs/detail-list', { params })),
  detailText: (params) => unwrap(request.get('/admin/logs/detail-text', { params })),
  detailClear: () => unwrap(request.post('/admin/logs/detail-clear')),
}
