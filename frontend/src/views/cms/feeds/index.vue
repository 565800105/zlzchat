<script setup>
import { reactive, ref, nextTick } from 'vue'
import { Message } from '@arco-design/web-vue'
import { feedsApi, articlesApi } from '@/api/modules'
import { useTaskCenter } from '@/stores/taskCenter'

const taskCenter = useTaskCenter()

/* ============================ 响应式状态 ============================ */
const loading = ref(false)
const tableData = ref([])
const pagination = reactive({ total: 0, pageNum: 1, pageSize: 10 })
const query = reactive({ mpName: '', wxsId: '', status: undefined })

// 编辑弹窗
const modalVisible = ref(false)
const editing = ref(false)
const formRef = ref()
const form = reactive({
  feed_id: undefined,
  mp_name: '',
  wxs_id: '',
  mp_cover: '',
  mp_intro: '',
  status: 2,
  show_count: 20,
  version: '',
})
const rules = {
  mp_name: [{ required: true, message: '请输入公众号名称' }],
  wxs_id: [{ required: true, message: '请输入 wxsId' }],
}

// 名称搜索添加弹窗（对应老系统「添加」）
const searchVisible = ref(false)
const searchLoading = ref(false)
const adding = ref(false)
const feedName = ref('')
const searchResults = ref([])
const selectedIndex = ref(null)

// 链接添加弹窗（对应老系统「链接添加」）
const linkVisible = ref(false)
const linkLoading = ref(false)
const linkUrl = ref('')

// 同步历史弹窗（对应老系统 hisType 单选 + 自定义起始/结束页）
const historyVisible = ref(false)
const currentHistoryFeed = ref(null)
const historyForm = reactive({ hisType: '1', startNum: 0, endNum: 20 })

// 页码必须是 20 的倍数，向上取整（21→40，18→20）
function normalizePage(value) {
  const n = Number(value)
  if (!Number.isFinite(n) || n <= 0) return 0
  return Math.ceil(n / 20) * 20
}
function onStartNumChange(value) {
  historyForm.startNum = normalizePage(value)
}
function onEndNumChange(value) {
  historyForm.endNum = normalizePage(value)
}

/* ============================ API 调用 ============================ */
async function loadData() {
  loading.value = true
  try {
    const res = await feedsApi.list({
      pageNum: pagination.pageNum,
      pageSize: pagination.pageSize,
      mpName: query.mpName || undefined,
      wxsId: query.wxsId || undefined,
      status: query.status,
    })
    tableData.value = res.list || []
    pagination.total = res.total || 0
  } finally {
    loading.value = false
  }
}

/* ============================ 查询与分页 ============================ */
function handleSearch() {
  pagination.pageNum = 1
  loadData()
}
function handleReset() {
  Object.assign(query, { mpName: '', wxsId: '', status: undefined })
  handleSearch()
}
function handlePageChange(page) {
  pagination.pageNum = page
  loadData()
}

/* ============================ 编辑（保留手填编辑） ============================ */
function resetForm() {
  Object.assign(form, {
    feed_id: undefined,
    mp_name: '',
    wxs_id: '',
    mp_cover: '',
    mp_intro: '',
    status: 2,
    show_count: 20,
    version: '',
  })
  formRef.value?.clearValidate()
}
function openEdit(row) {
  editing.value = true
  resetForm()
  Object.assign(form, row)
  modalVisible.value = true
}
async function submitForm() {
  try {
    await formRef.value?.validate()
  } catch (e) {
    return
  }
  const payload = {
    feed_id: form.feed_id,
    mp_name: form.mp_name,
    wxs_id: form.wxs_id,
    mp_cover: form.mp_cover,
    mp_intro: form.mp_intro,
    status: form.status,
    show_count: form.show_count,
    version: form.version,
  }
  await feedsApi.edit(payload)
  Message.success('修改成功')
  modalVisible.value = false
  loadData()
}
async function removeRow(row) {
  await feedsApi.remove([row.feed_id])
  Message.success('删除成功')
  loadData()
}

/* ============================ 名称搜索添加 ============================ */
function openSearch() {
  searchVisible.value = true
  feedName.value = ''
  searchResults.value = []
  selectedIndex.value = null
}
async function doSearch() {
  if (!feedName.value || feedName.value.trim().length < 2) {
    Message.warning('请输入至少两个字符的公众号名称')
    return
  }
  searchLoading.value = true
  try {
    const data = await feedsApi.searchFeed(feedName.value.trim())
    searchResults.value = Array.isArray(data) ? data : []
    selectedIndex.value = null
    if (!searchResults.value.length) Message.info('未搜索到相关公众号')
  } catch (e) {
    /* 拦截器已统一提示 */
  } finally {
    searchLoading.value = false
  }
}
function selectFeed(index) {
  selectedIndex.value = index
}
async function submitAddFeed() {
  const feed = searchResults.value[selectedIndex.value]
  if (!feed) {
    Message.warning('请先搜索并选择一个公众号')
    return
  }
  adding.value = true
  try {
    const bookInfo = feed.bookInfo || feed
    await feedsApi.addFeed(bookInfo)
    Message.success('添加成功')
    searchVisible.value = false
    loadData()
  } catch (e) {
    /* 拦截器已统一提示 */
  } finally {
    adding.value = false
  }
}

/* ============================ 链接添加 ============================ */
function openLink() {
  linkVisible.value = true
  linkUrl.value = ''
}
async function submitLink() {
  if (!linkUrl.value || !linkUrl.value.trim()) {
    Message.warning('请输入文章链接')
    return
  }
  linkLoading.value = true
  try {
    await feedsApi.addLinkFeed(linkUrl.value.trim())
    Message.success('添加成功')
    linkVisible.value = false
    loadData()
  } catch (e) {
    /* 拦截器已统一提示 */
  } finally {
    linkLoading.value = false
  }
}

/* ============================ OPML 导出 ============================ */
async function exportOpml() {
  try {
    const blob = await feedsApi.downloadOpml()
    const href = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = href
    a.download = 'zlzchat.opml'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(href)
    Message.success('OPML 文件已导出')
  } catch (e) {
    Message.error('导出失败：' + (e?.message || '未知错误'))
  }
}

/* ============================ 同步操作（均在列表行内触发） ============================ */
async function handleSyncLatestRow(row) {
  const { id, backendId } = taskCenter.start({
    title: '最新同步',
    detail: `${row.mp_name || row.wxs_id}`,
  })
  await nextTick()
  const started = Date.now()
  try {
    const res = await articlesApi.syncLatest(row.wxs_id, backendId)
    const added = res?.updateNum ?? 0
    const cost = ((Date.now() - started) / 1000).toFixed(1)
    taskCenter.finish(id, {
      status: 'success',
      msg: `已新增 ${added} 条 · 耗时 ${cost}s`,
      updateNum: added,
    })
    Message.success(`同步完成，已新增 ${added} 条`)
    loadData()
  } catch (e) {
    taskCenter.finish(id, { status: 'error', msg: e?.message || '同步最新失败' })
  }
}
function openSyncHistory(row) {
  currentHistoryFeed.value = row
  historyForm.hisType = '1'
  historyForm.startNum = 0
  historyForm.endNum = 20
  historyVisible.value = true
}
async function submitSyncHistory() {
  const feed = currentHistoryFeed.value
  const { id, backendId } = taskCenter.start({
    title: '历史同步',
    detail: `${feed?.mp_name || feed?.wxs_id} · 第${historyForm.startNum}-${historyForm.endNum}篇`,
  })
  historyVisible.value = false
  await nextTick()
  const started = Date.now()
  try {
    const startNum = normalizePage(historyForm.startNum)
    const endNum = normalizePage(historyForm.endNum)
    const res = await articlesApi.syncHistory(feed.wxs_id, {
      hisType: historyForm.hisType,
      startNum,
      endNum,
      taskId: backendId,
    })
    const added = res?.updateNum ?? 0
    const cost = ((Date.now() - started) / 1000).toFixed(1)
    taskCenter.finish(id, {
      status: 'success',
      msg: `已新增 ${added} 条 · 耗时 ${cost}s`,
      updateNum: added,
    })
    Message.success(`同步完成，已新增 ${added} 条`)
    loadData()
  } catch (e) {
    taskCenter.finish(id, { status: 'error', msg: e?.message || '同步历史失败' })
  }
}
async function handleClearArticles(row) {
  const count = await articlesApi.clearFeedArticles(row.wxs_id)
  Message.success(`已清空 ${count ?? 0} 篇文章`)
  loadData()
}

/* ============================ 表格列 ============================ */
const columns = [
  { title: '公众号', dataIndex: 'mp_name', slotName: 'mp_name', width: 220 },
  { title: 'wxsId', dataIndex: 'wxs_id', width: 150 },
  { title: '状态', dataIndex: 'status', slotName: 'status', width: 110 },
  { title: '文章数', dataIndex: 'articleNum', width: 90 },
  { title: '显示条数', dataIndex: 'show_count', width: 100 },
  { title: '版本', dataIndex: 'version', slotName: 'version', width: 140, ellipsis: true },
  { title: '更新次数', dataIndex: 'update_count', width: 100 },
  { title: '同步时间', dataIndex: 'sync_time', slotName: 'sync_time', width: 170 },
  { title: '操作', dataIndex: 'actions', slotName: 'actions', width: 320, fixed: 'right' },
]

loadData()
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h2 class="page-title">公众号信息</h2>
        <p class="page-desc">管理公众号订阅源及文章同步</p>
      </div>
      <a-space wrap>
        <a-button type="primary" @click="openSearch">+ 添加</a-button>
        <a-button @click="openLink">链接添加</a-button>
        <a-button @click="exportOpml">opml文件</a-button>
      </a-space>
    </div>

    <!-- 搜索栏 -->
    <div class="search-bar">
      <a-form layout="inline" :model="query" @submit="handleSearch">
        <a-form-item label="公众号名称">
          <a-input v-model="query.mpName" placeholder="公众号名称" allow-clear />
        </a-form-item>
        <a-form-item label="wxsId">
          <a-input v-model="query.wxsId" placeholder="wxsId" allow-clear />
        </a-form-item>
        <a-form-item label="状态">
          <a-select v-model="query.status" placeholder="全部" allow-clear style="width: 130px">
            <a-option :value="1">不拉取</a-option>
            <a-option :value="2">自动拉取</a-option>
          </a-select>
        </a-form-item>
        <a-form-item>
          <a-button type="primary" @click="handleSearch">查询</a-button>
          <a-button style="margin-left: 8px" @click="handleReset">重置</a-button>
        </a-form-item>
      </a-form>
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
        row-key="feed_id"
        :scroll="{ x: 1200 }"
        @page-change="handlePageChange"
      >
        <template #mp_name="{ record }">
          <a-space :size="10">
            <img v-if="record.mp_cover" :src="record.mp_cover" class="cell-thumb" />
            <span v-else class="cell-thumb-fallback">无图</span>
            <span>{{ record.mp_name }}</span>
          </a-space>
        </template>
        <template #status="{ record }">
          <a-tag :color="record.status === 1 ? 'gray' : 'green'">
            {{ record.status === 1 ? '不拉取' : '自动拉取' }}
          </a-tag>
        </template>
        <template #version="{ record }">
          <span class="mono text-muted">{{ record.version || '-' }}</span>
        </template>
        <template #sync_time="{ record }">
          <span class="text-muted">{{ record.sync_time || '-' }}</span>
        </template>
        <template #actions="{ record }">
          <a-space wrap>
            <a-button type="text" size="small" @click="handleSyncLatestRow(record)">最新同步</a-button>
            <a-button type="text" size="small" @click="openSyncHistory(record)">历史同步</a-button>
            <a-popconfirm content="确认清空该公众号的全部文章？" @ok="handleClearArticles(record)">
              <a-button type="text" size="small" status="danger">清空文章</a-button>
            </a-popconfirm>
            <a-button type="text" size="small" @click="openEdit(record)">编辑</a-button>
            <a-popconfirm content="确认删除该公众号？" @ok="removeRow(record)">
              <a-button type="text" size="small" status="danger">删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </a-table>
    </div>

    <!-- 编辑弹窗 -->
    <a-modal
      v-model:visible="modalVisible"
      :title="editing ? '编辑公众号' : '编辑公众号'"
      :width="560"
      @ok="submitForm"
      @cancel="modalVisible = false"
    >
      <a-form ref="formRef" :model="form" :rules="rules" layout="vertical">
        <div class="form-grid">
          <a-form-item field="mp_name" label="公众号名称">
            <a-input v-model="form.mp_name" placeholder="公众号名称" />
          </a-form-item>
          <a-form-item field="status" label="拉取状态">
            <a-select v-model="form.status" style="width: 100%">
              <a-option :value="1">不拉取</a-option>
              <a-option :value="2">自动拉取</a-option>
            </a-select>
          </a-form-item>
          <a-form-item field="show_count" label="显示条数">
            <a-input-number v-model="form.show_count" :min="0" style="width: 100%" />
          </a-form-item>
          <a-form-item field="version" label="版本号">
            <a-input v-model="form.version" placeholder="版本号（可选）" />
          </a-form-item>
        </div>
        <a-form-item field="mp_intro" label="公众号简介">
          <a-textarea v-model="form.mp_intro" placeholder="公众号简介" :rows="3" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 名称搜索添加弹窗 -->
    <a-modal
      v-model:visible="searchVisible"
      title="公众号添加"
      :width="640"
      :footer="false"
      @cancel="searchVisible = false"
    >
      <div class="add-box">
        <a-space>
          <a-input
            v-model="feedName"
            placeholder="请输入公众号全称"
            allow-clear
            style="width: 360px"
            @press-enter="doSearch"
          />
          <a-button type="primary" :loading="searchLoading" @click="doSearch">搜索</a-button>
        </a-space>
        <div class="feed-grid">
          <div
            v-for="(feed, index) in searchResults"
            :key="index"
            class="feed-item"
            :class="{ active: selectedIndex === index }"
            @click="selectFeed(index)"
          >
            <div class="feed-avatar-wrap">
              <img
                v-if="(feed.bookInfo || feed).cover"
                :src="(feed.bookInfo || feed).cover"
                class="feed-avatar"
              />
              <div v-else class="feed-avatar feed-avatar-fallback">无图</div>
            </div>
            <div class="feed-name">{{ (feed.bookInfo || feed).title }}</div>
          </div>
          <div v-if="!searchResults.length" class="feed-empty">
            {{ searchLoading ? '搜索中...' : '请输入公众号名称并搜索' }}
          </div>
        </div>
        <div class="add-footer">
          <a-button @click="searchVisible = false">取消</a-button>
          <a-button type="primary" :loading="adding" @click="submitAddFeed">确定</a-button>
        </div>
      </div>
    </a-modal>

    <!-- 链接添加弹窗 -->
    <a-modal
      v-model:visible="linkVisible"
      title="公众号链接添加"
      :width="480"
      :confirm-loading="linkLoading"
      @ok="submitLink"
      @cancel="linkVisible = false"
    >
      <a-textarea v-model="linkUrl" placeholder="请输入文章链接" :rows="4" />
    </a-modal>

    <!-- 同步历史弹窗 -->
    <a-modal
      v-model:visible="historyVisible"
      title="历史同步"
      :width="480"
      @ok="submitSyncHistory"
      @cancel="historyVisible = false"
    >
      <div class="form-tip" style="margin-bottom: 12px">
        公众号：{{ currentHistoryFeed?.mp_name }}
      </div>
      <a-form layout="vertical" :model="historyForm">
        <a-form-item>
          <a-radio-group v-model="historyForm.hisType" type="button">
            <a-radio value="1">全部拉取（由数据库存储最后拉取页）</a-radio>
            <a-radio value="2">自定义</a-radio>
          </a-radio-group>
        </a-form-item>
        <div v-if="historyForm.hisType === '1'" class="form-tip history-page-tip">
          当前数据库记录的拉取页：<strong>第 {{ currentHistoryFeed?.update_count || 0 }} 页</strong>
          <span class="form-help">（全部拉取将从该页继续，每完成一页自动回写）</span>
        </div>
        <div v-if="historyForm.hisType === '2'" class="form-grid">
          <a-form-item label="开始页">
            <a-input-number
              v-model="historyForm.startNum"
              :min="0"
              :step="20"
              style="width: 100%"
              @change="onStartNumChange"
            />
            <div class="form-help">代表开始页数，必须是 20 的倍数（输入后自动向上取整）</div>
          </a-form-item>
          <a-form-item label="结束页">
            <a-input-number
              v-model="historyForm.endNum"
              :min="0"
              :step="20"
              style="width: 100%"
              @change="onEndNumChange"
            />
            <div class="form-help">代表结束页数，必须是 20 的倍数（输入后自动向上取整）</div>
          </a-form-item>
        </div>
      </a-form>
    </a-modal>
  </div>
</template>

<style scoped>
.add-box {
  padding: 4px 0;
}
.form-help {
  font-size: 12px;
  color: var(--color-text-3);
  margin-top: 4px;
}
.history-page-tip {
  margin: -4px 0 12px;
  padding: 8px 12px;
  background: #f2f7ff;
  border-radius: 6px;
  color: #1d2b42;
  font-size: 13px;
}
.history-page-tip strong {
  color: #2f6ef5;
}
.history-page-tip .form-help {
  display: block;
}
.feed-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-top: 18px;
  min-height: 160px;
  max-height: 360px;
  overflow-y: auto;
}
.feed-item {
  width: 120px;
  display: flex;
  flex-direction: column;
  align-items: center;
  cursor: pointer;
  padding: 10px 6px;
  border: 2px solid transparent;
  border-radius: 10px;
  transition: all 0.2s;
}
.feed-item:hover {
  background: var(--color-fill-1);
}
.feed-item.active {
  border-color: rgb(var(--primary-6));
  background: var(--color-primary-light-1);
}
.feed-avatar-wrap {
  width: 84px;
  height: 84px;
  border-radius: 50%;
  overflow: hidden;
  margin-bottom: 10px;
  background: var(--color-fill-2);
}
.feed-avatar {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.feed-avatar-fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-3);
  font-size: 12px;
}
.feed-name {
  font-size: 13px;
  max-width: 110px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  text-align: center;
}
.feed-empty {
  width: 100%;
  text-align: center;
  color: var(--color-text-3);
  padding: 50px 0;
}
.add-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid var(--color-border-2);
}
</style>
