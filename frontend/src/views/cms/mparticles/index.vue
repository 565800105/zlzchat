<script setup>
import { reactive, ref, computed, onMounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import { articlesApi, feedsApi } from '@/api/modules'

/* ============================ 响应式状态 ============================ */
const loading = ref(false)
const tableData = ref([])
const pagination = reactive({ total: 0, pageNum: 1, pageSize: 10 })
const query = reactive({ title: '', wxsId: '', readType: '' })
const dateRange = ref([])

// 左侧公众号列表
const feedList = ref([])
const feedLoading = ref(false)
const feedKeyword = ref('')
const filteredFeeds = computed(() => {
  const kw = feedKeyword.value.trim().toLowerCase()
  if (!kw) return feedList.value
  return feedList.value.filter((f) => (f.mp_name || '').toLowerCase().includes(kw))
})

// 详情弹窗
const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref({})

// 微信正文图片(mmbiz.qpic.cn 等)有防盗链，浏览器直连会显示"未经允许不可引用"。
// 统一改写为后端图片代理路径，由后端带微信 Referer 转发。
function proxyWxImages(html) {
  if (!html) return html
  return html.replace(
    /((?:src|data-src)\s*=\s*["'])(https?:\/\/[^"']+)(["'])/gi,
    (match, prefix, url, suffix) => {
      try {
        const host = new URL(url).hostname.toLowerCase()
        if (/(^|\.)(qpic\.cn|qlogo\.cn|gtimg\.com|qq\.com)$/.test(host)) {
          return `${prefix}/api/open/image-proxy?url=${encodeURIComponent(url)}${suffix}`
        }
      } catch (e) {
        /* 非法 URL 保持原样 */
      }
      return match
    },
  )
}
const contentHtml = computed(
  () => proxyWxImages(detail.value.content) || '<span class="text-muted">暂无正文</span>',
)

// 单张图片 URL（列表封面等）：微信 CDN 图走代理，其余原样
function imageUrl(url) {
  if (!url) return ''
  try {
    const host = new URL(url, window.location.origin).hostname.toLowerCase()
    if (/(^|\.)(qpic\.cn|qlogo\.cn|gtimg\.com|qq\.com)$/.test(host)) {
      return `/api/open/image-proxy?url=${encodeURIComponent(url)}`
    }
  } catch (e) {
    /* 非法 URL 原样返回 */
  }
  return url
}

/* ============================ API 调用 ============================ */
async function loadData() {
  loading.value = true
  try {
    const res = await articlesApi.list({
      pageNum: pagination.pageNum,
      pageSize: pagination.pageSize,
      title: query.title || undefined,
      wxsId: query.wxsId || undefined,
      readType: query.readType || undefined,
      beginTime: dateRange.value?.[0] || undefined,
      endTime: dateRange.value?.[1] ? `${dateRange.value[1]} 23:59:59` : undefined,
    })
    tableData.value = res.list || []
    pagination.total = res.total || 0
  } finally {
    loading.value = false
  }
}

async function loadFeeds() {
  feedLoading.value = true
  try {
    const data = await feedsApi.all()
    feedList.value = Array.isArray(data) ? data : []
  } finally {
    feedLoading.value = false
  }
}

/* ============================ 事件处理 ============================ */
function handleSearch() {
  pagination.pageNum = 1
  loadData()
}
function handleReset() {
  Object.assign(query, { title: '', wxsId: '', readType: '' })
  dateRange.value = []
  handleSearch()
}
function handlePageChange(page) {
  pagination.pageNum = page
  loadData()
}

// 点击左侧公众号：按 wxsId 过滤，再次点击取消
function selectFeed(feed) {
  if (query.wxsId === feed.wxs_id) {
    query.wxsId = ''
  } else {
    query.wxsId = feed.wxs_id
  }
  pagination.pageNum = 1
  loadData()
}
function clearFeedFilter() {
  query.wxsId = ''
  pagination.pageNum = 1
  loadData()
}
function currentFeedName() {
  const f = feedList.value.find((x) => x.wxs_id === query.wxsId)
  return f?.mp_name || query.wxsId || ''
}

async function removeRow(row) {
  await articlesApi.remove([row.articles_id])
  Message.success('删除成功')
  loadData()
}
async function handleReFetch(row) {
  await articlesApi.reFetch(row.articles_id)
  Message.success('正文抓取完成')
}
async function openDetail(row) {
  detailVisible.value = true
  detailLoading.value = true
  detail.value = {}
  try {
    detail.value = await articlesApi.get(row.articles_id)
    // 对照老系统 goUrl：查看后标记为已读(readType=1)，并刷新列表使标题变灰
    if (String(row.read_type) !== '1') {
      try {
        await articlesApi.edit({
          articles_id: row.articles_id,
          read_type: '1',
        })
        row.read_type = '1'
        loadData()
      } catch (e) {
        /* 标记失败不影响查看 */
      }
    }
  } finally {
    detailLoading.value = false
  }
}

/* ============================ 表格列 ============================ */
const columns = [
  { title: '标题', dataIndex: 'title', slotName: 'title', width: 260, ellipsis: true },
  { title: '公众号', dataIndex: 'mp_name', slotName: 'mp_name', width: 180 },
  { title: 'wxsId', dataIndex: 'wxs_id', width: 130 },
  { title: '发布时间', dataIndex: 'publish_time', slotName: 'publish_time', width: 170 },
  { title: '阅读状态', dataIndex: 'read_type', slotName: 'read_type', width: 100 },
  { title: '封面', dataIndex: 'pic_url', slotName: 'pic_url', width: 80 },
  { title: '操作', dataIndex: 'actions', slotName: 'actions', width: 200, fixed: 'right' },
]

onMounted(() => {
  loadFeeds()
})
loadData()
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h2 class="page-title">文章信息</h2>
        <p class="page-desc">查看与管理采集到的公众号文章</p>
      </div>
    </div>

    <div class="mp-layout">
      <!-- 左侧公众号列表 -->
      <aside class="mp-sidebar">
        <div class="mp-sidebar-header">
          <span class="mp-sidebar-title">公众号列表</span>
          <span class="mp-sidebar-count">{{ feedList.length }}</span>
        </div>
        <div class="mp-sidebar-search">
          <a-input
            v-model="feedKeyword"
            placeholder="搜索公众号名称"
            allow-clear
            size="small"
          />
        </div>
        <a-spin :loading="feedLoading" class="mp-list-spin">
          <div class="mp-list">
            <div
              class="mp-item"
              :class="{ active: !query.wxsId }"
              @click="clearFeedFilter"
            >
              <span class="mp-avatar mp-avatar-all">全</span>
              <span class="mp-item-name">全部公众号</span>
              <span class="mp-item-count">{{ feedList.reduce((s, f) => s + (f.articleNum || 0), 0) }}</span>
            </div>
            <div
              v-for="feed in filteredFeeds"
              :key="feed.feed_id"
              class="mp-item"
              :class="{ active: query.wxsId === feed.wxs_id }"
              @click="selectFeed(feed)"
            >
              <img v-if="feed.mp_cover" :src="feed.mp_cover" class="mp-avatar" />
              <span v-else class="mp-avatar mp-avatar-fallback">无图</span>
              <span class="mp-item-name" :title="feed.mp_name">{{ feed.mp_name }}</span>
              <span class="mp-item-count">{{ feed.articleNum || 0 }}</span>
            </div>
            <div v-if="!filteredFeeds.length" class="mp-list-empty">无匹配公众号</div>
          </div>
        </a-spin>
      </aside>

      <!-- 右侧主内容 -->
      <div class="mp-main">
        <!-- 搜索栏 -->
        <div class="search-bar">
          <a-form layout="inline" :model="query" @submit="handleSearch">
            <a-form-item label="标题">
              <a-input v-model="query.title" placeholder="文章标题" allow-clear />
            </a-form-item>
            <a-form-item label="阅读类型">
              <a-select v-model="query.readType" placeholder="全部" allow-clear style="width: 110px">
                <a-option value="0">未读</a-option>
                <a-option value="1">已读</a-option>
              </a-select>
            </a-form-item>
            <a-form-item label="发布时间">
              <a-range-picker v-model="dateRange" value-format="YYYY-MM-DD" style="width: 240px" />
            </a-form-item>
            <a-form-item>
              <a-button type="primary" @click="handleSearch">查询</a-button>
              <a-button style="margin-left: 8px" @click="handleReset">重置</a-button>
            </a-form-item>
          </a-form>
        </div>

        <!-- 当前过滤提示 -->
        <div v-if="query.wxsId" class="filter-tip">
          当前公众号：<b>{{ currentFeedName() }}</b>
          <a-button type="text" size="small" @click="clearFeedFilter">清除过滤</a-button>
        </div>

        <!-- 列表 -->
        <div class="table-card">
          <a-table
            :columns="columns"
            :data="tableData"
            :loading="loading"
            :pagination="{
              total: pagination.total,
              current: pagination.pageNum,
              pageSize: pagination.pageSize,
              showTotal: true,
            }"
            row-key="articles_id"
            :scroll="{ x: 1380 }"
            @page-change="handlePageChange"
          >
            <template #title="{ record }">
              <a-button type="text" size="small" @click="openDetail(record)">
                <span
                  class="text-ellipsis"
                  :class="{ 'article-read': String(record.read_type) === '1' }"
                  :title="record.title"
                >
                  {{ record.title }}
                </span>
              </a-button>
            </template>
            <template #mp_name="{ record }">
              <a-space :size="8">
                <img v-if="record.mp_cover || record.mpCover" :src="record.mp_cover || record.mpCover" class="cell-thumb" />
                <span v-else class="cell-thumb-fallback">无图</span>
                <span>{{ record.mp_name || record.mpName || '-' }}</span>
              </a-space>
            </template>
            <template #pic_url="{ record }">
              <img v-if="record.pic_url" :src="imageUrl(record.pic_url)" class="cell-thumb" />
              <span v-else class="cell-thumb-fallback">无图</span>
            </template>
            <template #publish_time="{ record }">
              <span class="text-muted">{{ record.publish_time || '-' }}</span>
            </template>
            <template #read_type="{ record }">
              <a-tag :color="String(record.read_type) === '1' ? 'green' : 'red'">
                {{ String(record.read_type) === '1' ? '已读' : '未读' }}
              </a-tag>
            </template>
            <template #links="{ record }">
              <a-link :href="record.links" target="_blank">{{ record.links }}</a-link>
            </template>
            <template #actions="{ record }">
              <a-space>
                <a-button type="text" size="small" @click="openDetail(record)">详情</a-button>
                <a-button type="text" size="small" @click="handleReFetch(record)">重抓正文</a-button>
                <a-popconfirm content="确认删除该文章？" @ok="removeRow(record)">
                  <a-button type="text" size="small" status="danger">删除</a-button>
                </a-popconfirm>
              </a-space>
            </template>
          </a-table>
        </div>
      </div>
    </div>

    <!-- 详情弹窗 -->
    <a-modal
      v-model:visible="detailVisible"
      title="文章详情"
      :width="760"
      :footer="false"
    >
      <a-spin :loading="detailLoading" style="width: 100%">
        <a-descriptions :column="2" bordered size="small" style="margin-bottom: 16px">
          <a-descriptions-item label="标题">{{ detail.title }}</a-descriptions-item>
          <a-descriptions-item label="公众号">{{ detail.mp_name }}</a-descriptions-item>
          <a-descriptions-item label="发布时间">{{ detail.publish_time }}</a-descriptions-item>
          <a-descriptions-item label="原文链接">
            <a-link v-if="detail.links" :href="detail.links" target="_blank">打开原文</a-link>
          </a-descriptions-item>
        </a-descriptions>

        <h4 class="detail-section-title">正文内容（富文本）</h4>
        <div class="rich-content" v-html="contentHtml"></div>

        <h4 class="detail-section-title">纯文本内容</h4>
        <div class="rich-content">{{ detail.content_text || '暂无文本内容' }}</div>
      </a-spin>
    </a-modal>
  </div>
</template>

<style scoped>
.mp-layout {
  display: flex;
  gap: 16px;
  align-items: stretch;
}
.mp-sidebar {
  width: 240px;
  flex: 0 0 240px;
  background: var(--color-bg-1);
  border: 1px solid var(--color-border-2);
  border-radius: var(--app-card-radius, 14px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  max-height: calc(100vh - 180px);
}
.mp-sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px 8px;
}
.mp-sidebar-title {
  font-weight: 600;
  font-size: 15px;
}
.mp-sidebar-count {
  font-size: 12px;
  color: var(--color-text-3);
  background: var(--color-fill-2);
  border-radius: 10px;
  padding: 1px 8px;
}
.mp-sidebar-search {
  padding: 4px 12px 12px;
}
.mp-list-spin {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
.mp-list {
  height: 100%;
  overflow-y: auto;
  padding: 0 8px 12px;
}
.mp-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
}
.mp-item:hover {
  background: var(--color-fill-1);
}
.mp-item.active {
  background: var(--color-primary-light-1);
}
.mp-item.active .mp-item-name {
  color: rgb(var(--primary-6));
  font-weight: 600;
}
.mp-avatar {
  width: 36px;
  height: 36px;
  flex: 0 0 36px;
  border-radius: 50%;
  object-fit: cover;
  background: var(--color-fill-2);
}
.mp-avatar-all,
.mp-avatar-fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  color: var(--color-text-3);
}
.mp-avatar-all {
  color: rgb(var(--primary-6));
  background: var(--color-primary-light-1);
  font-weight: 600;
}
.mp-item-name {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.mp-item-count {
  font-size: 12px;
  color: var(--color-text-3);
  background: var(--color-fill-2);
  border-radius: 10px;
  padding: 1px 7px;
}
.mp-list-empty {
  text-align: center;
  color: var(--color-text-3);
  font-size: 13px;
  padding: 24px 0;
}
.mp-main {
  flex: 1;
  min-width: 0;
}
.filter-tip {
  background: var(--color-primary-light-1);
  border-radius: 8px;
  padding: 8px 14px;
  margin-bottom: 12px;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.article-read {
  color: var(--color-text-4) !important;
  text-decoration: line-through;
  text-decoration-color: var(--color-text-4);
}
.detail-section-title {
  margin: 16px 0 8px;
  font-size: 14px;
  color: var(--app-text-2);
}
</style>
