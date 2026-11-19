<script setup>
import { reactive, ref, computed } from 'vue'
import { Message } from '@arco-design/web-vue'
import { IconUpload, IconDownload, IconCopy } from '@arco-design/web-vue/es/icon'
import { classificationApi, feedsApi } from '@/api/modules'

/* ============================ 响应式状态 ============================ */
// 图标上传相关
const iconUploading = ref(false)

// 订阅源地址弹窗
const rssModalVisible = ref(false)
const rssType = ref('atom') // atom / rss
const currentRssClassification = ref(null)
const rssUrl = computed(() => {
  if (!currentRssClassification.value) return ''
  const id = currentRssClassification.value.classification_id
  const path = rssType.value === 'rss' ? 'mpClassificationRss' : 'mpClassificationAtom'
  return `${window.location.origin}/api/open/${path}/${id}`
})

const loading = ref(false)
const tableData = ref([])
const pagination = reactive({ total: 0, pageNum: 1, pageSize: 10 })
const query = reactive({ classificationName: '' })

// 新增/编辑弹窗
const modalVisible = ref(false)
const editing = ref(false)
const formRef = ref()
const form = reactive({
  classification_id: undefined,
  classification_name: '',
  show_count: 20,
  icon: '',
  remark: '',
})
const rules = {
  classification_name: [{ required: true, message: '请输入分类名称' }],
}

// 明细抽屉
const drawerVisible = ref(false)
const detailLoading = ref(false)
const detailData = ref([])
const currentClassification = ref(null)
const detailSelectedKeys = ref([]) // 明细表勾选(用于删除)
// 公众号勾选添加：全部公众号 + 输入筛选
const allFeeds = ref([])
const feedFilter = reactive({ wxsId: '', mpName: '' })
const feedSelectedKeys = ref([])
const feedLoading = ref(false)
const filteredFeeds = computed(() => {
  const kw = (feedFilter.mpName || '').trim().toLowerCase()
  const wid = (feedFilter.wxsId || '').trim().toLowerCase()
  return allFeeds.value.filter((f) => {
    if (kw && !String(f.mp_name || '').toLowerCase().includes(kw)) return false
    if (wid && !String(f.wxs_id || '').toLowerCase().includes(wid)) return false
    return true
  })
})

/* ============================ API 调用 ============================ */
async function loadData() {
  loading.value = true
  try {
    const res = await classificationApi.list({
      pageNum: pagination.pageNum,
      pageSize: pagination.pageSize,
      classificationName: query.classificationName || undefined,
    })
    tableData.value = res.list || []
    pagination.total = res.total || 0
  } finally {
    loading.value = false
  }
}

async function loadDetail() {
  if (!currentClassification.value) return
  detailLoading.value = true
  try {
    detailData.value =
      (await classificationApi.detailList(currentClassification.value.classification_id)) || []
  } finally {
    detailLoading.value = false
  }
}

/* ============================ 事件处理：主表 ============================ */
function handleSearch() {
  pagination.pageNum = 1
  loadData()
}

function handleReset() {
  query.classificationName = ''
  handleSearch()
}

function handlePageChange(page) {
  pagination.pageNum = page
  loadData()
}

/* ============================ 图标上传 ============================ */
async function handleIconUpload(options) {
  // Arco custom-request 参数：{ fileItem, action, name, onProgress, onSuccess, onError }
  // 原生 File 在 options.fileItem.file
  const raw = options?.fileItem?.file
  if (!raw) {
    options?.onError?.(new Error('无法读取所选文件'))
    Message.error('无法读取所选文件')
    return
  }
  iconUploading.value = true
  try {
    const res = await classificationApi.uploadIcon(raw)
    form.icon = res?.url || ''
    Message.success('图标上传成功')
    options?.onSuccess?.(res)
  } catch (e) {
    options?.onError?.(e)
  } finally {
    iconUploading.value = false
  }
}

function handleIconRemove() {
  form.icon = ''
}

/* ============================ 订阅源地址 / OPML ============================ */
function openRss(row) {
  currentRssClassification.value = row
  rssType.value = 'atom'
  rssModalVisible.value = true
}

async function copyRssUrl() {
  try {
    await navigator.clipboard.writeText(rssUrl.value)
    Message.success('订阅源地址已复制')
  } catch (e) {
    // 回退：选中文本手动复制
    Message.warning('复制失败，请手动选择地址复制')
  }
}

async function exportOpml() {
  try {
    const blob = await classificationApi.downloadOpml(rssType.value === 'rss' ? 'rss' : 'atom')
    const href = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = href
    a.download = 'zlzchatcategory.opml'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(href)
    Message.success('OPML 文件已导出')
  } catch (e) {
    Message.error('导出失败：' + (e?.message || '未知错误'))
  }
}

function resetForm() {
  Object.assign(form, {
    classification_id: undefined,
    classification_name: '',
    show_count: 20,
    icon: '',
    remark: '',
  })
  formRef.value?.clearValidate()
}

function openAdd() {
  editing.value = false
  resetForm()
  modalVisible.value = true
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
    classification_name: form.classification_name,
    show_count: form.show_count,
    icon: form.icon,
    remark: form.remark,
  }
  if (editing.value) {
    payload.classification_id = form.classification_id
    await classificationApi.edit(payload)
    Message.success('修改成功')
  } else {
    await classificationApi.add(payload)
    Message.success('新增成功')
  }
  modalVisible.value = false
  loadData()
}

async function removeRow(row) {
  await classificationApi.remove([row.classification_id])
  Message.success('删除成功')
  loadData()
}

/* ============================ 事件处理：明细 ============================ */
async function loadAllFeeds() {
  feedLoading.value = true
  try {
    allFeeds.value = (await feedsApi.all()) || []
  } finally {
    feedLoading.value = false
  }
}

function openDetail(row) {
  currentClassification.value = row
  detailSelectedKeys.value = []
  feedSelectedKeys.value = []
  feedFilter.wxsId = ''
  feedFilter.mpName = ''
  drawerVisible.value = true
  loadDetail()
  loadAllFeeds()
}

async function submitDetailAdd() {
  if (!feedSelectedKeys.value.length) {
    Message.warning('请先勾选要添加的公众号')
    return
  }
  await classificationApi.detailAdd({
    classification_id: currentClassification.value.classification_id,
    remark: feedSelectedKeys.value.join(','),
  })
  Message.success('添加成功')
  feedSelectedKeys.value = []
  loadDetail()
}

async function removeDetail() {
  if (!detailSelectedKeys.value.length) {
    Message.warning('请先选择要删除的明细')
    return
  }
  await classificationApi.detailRemove(detailSelectedKeys.value)
  Message.success('删除成功')
  detailSelectedKeys.value = []
  loadDetail()
}

/* ============================ 表格列 ============================ */
const columns = [
  { title: '分类名称', dataIndex: 'classification_name', width: 160 },
  { title: '显示条数', dataIndex: 'show_count', width: 100 },
  { title: '公众号数', dataIndex: 'feedCount', slotName: 'feedCount', width: 100 },
  { title: '图标', dataIndex: 'icon', slotName: 'icon', width: 90 },
  { title: '备注', dataIndex: 'remark', ellipsis: true },
  { title: '创建时间', dataIndex: 'create_time', slotName: 'create_time', width: 170 },
  { title: '操作', dataIndex: 'actions', slotName: 'actions', width: 260, fixed: 'right' },
]

// 公众号勾选候选列表
const feedColumns = [
  { title: '封面', dataIndex: 'mp_cover', slotName: 'mp_cover', width: 70 },
  { title: '公众号名称', dataIndex: 'mp_name', width: 160, ellipsis: true },
  { title: 'wxsId', dataIndex: 'wxs_id', width: 180, ellipsis: true },
  { title: '文章数', dataIndex: 'articleNum', width: 90 },
]

const detailColumns = [
  { title: '公众号', dataIndex: 'mp_name', width: 160 },
  { title: '封面', dataIndex: 'mp_cover', slotName: 'mp_cover', width: 80 },
  { title: 'wxsId', dataIndex: 'wxs_id', width: 160 },
  { title: 'feedId', dataIndex: 'feed_id', width: 120, ellipsis: true },
  { title: '备注', dataIndex: 'remark', slotName: 'remark', ellipsis: true },
]

// 首次加载
loadData()
</script>

<template>
  <div class="page-container">
    <!-- 标题栏 -->
    <div class="page-header">
      <div>
        <h2 class="page-title">订阅源分类</h2>
        <p class="page-desc">管理公众号订阅源的分类及其下的公众号明细</p>
      </div>
      <a-space>
        <a-button @click="exportOpml">
          <template #icon><IconDownload /></template>
          下载 OPML
        </a-button>
        <a-button type="primary" @click="openAdd">+ 新增分类</a-button>
      </a-space>
    </div>

    <!-- 搜索栏 -->
    <div class="search-bar">
      <a-form layout="inline" :model="query" @submit="handleSearch">
        <a-form-item label="分类名称">
          <a-input
            v-model="query.classificationName"
            placeholder="请输入分类名称"
            allow-clear
            @press-enter="handleSearch"
          />
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
          showJumper: true,
        }"
        row-key="classification_id"
        :scroll="{ x: 1000 }"
        @page-change="handlePageChange"
      >
        <template #feedCount="{ record }">
          <a-tag color="arcoblue">{{ record.feedCount ?? 0 }}</a-tag>
        </template>

        <template #icon="{ record }">
          <img v-if="record.icon" :src="record.icon" class="icon-thumb" />
          <span v-else class="text-muted">-</span>
        </template>

        <template #create_time="{ record }">
          <span class="text-muted">{{ record.create_time }}</span>
        </template>

        <template #actions="{ record }">
          <a-space>
            <a-button type="text" size="small" @click="openDetail(record)">明细</a-button>
            <a-button type="text" size="small" @click="openRss(record)">订阅源</a-button>
            <a-button type="text" size="small" @click="openEdit(record)">编辑</a-button>
            <a-popconfirm content="确认删除该分类？" @ok="removeRow(record)">
              <a-button type="text" size="small" status="danger">删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </a-table>
    </div>

    <!-- 新增/编辑弹窗 -->
    <a-modal
      v-model:visible="modalVisible"
      :title="editing ? '编辑分类' : '新增分类'"
      :width="520"
      @ok="submitForm"
      @cancel="modalVisible = false"
    >
      <a-form ref="formRef" :model="form" :rules="rules" layout="vertical">
        <a-form-item field="classification_name" label="分类名称">
          <a-input v-model="form.classification_name" placeholder="请输入分类名称" />
        </a-form-item>
        <a-form-item field="show_count" label="显示条数">
          <a-input-number v-model="form.show_count" :min="0" style="width: 100%" />
        </a-form-item>
        <a-form-item field="icon" label="分类图标">
          <a-space direction="vertical" :size="8">
            <a-upload
              :show-file-list="false"
              :disabled="iconUploading"
              accept="image/*"
              :custom-request="handleIconUpload"
            >
              <template #upload-button>
                <a-button :loading="iconUploading">
                  <template #icon><IconUpload /></template>
                  {{ iconUploading ? '上传中...' : '点击上传图标' }}
                </a-button>
              </template>
            </a-upload>
            <div v-if="form.icon" class="icon-preview">
              <img :src="form.icon" alt="图标预览" />
              <a-button type="text" size="small" status="danger" @click="handleIconRemove">移除</a-button>
            </div>
            <span v-else class="text-muted icon-hint">支持 png/jpg/gif/webp/svg/ico，不超过 5MB</span>
          </a-space>
        </a-form-item>
        <a-form-item field="remark" label="备注">
          <a-textarea v-model="form.remark" placeholder="请输入备注" :rows="3" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 订阅源地址弹窗：切换 RSS / Atom -->
    <a-modal
      v-model:visible="rssModalVisible"
      :title="`订阅源地址 · ${currentRssClassification?.classification_name || ''}`"
      :width="640"
      :footer="false"
    >
      <div class="rss-modal-body">
        <a-radio-group v-model="rssType" type="button" class="rss-type-switch">
          <a-radio value="atom">Atom 订阅源</a-radio>
          <a-radio value="rss">RSS 2.0 订阅源</a-radio>
        </a-radio-group>

        <p class="text-muted rss-hint">
          将下面的地址复制到 RSS 阅读器中即可订阅该分类下公众号的最新文章。
        </p>

        <a-input :model-value="rssUrl" readonly class="rss-url-input" />
        <div class="rss-actions">
          <a-space>
            <a-button type="primary" @click="copyRssUrl">
              <template #icon><IconCopy /></template>
              复制地址
            </a-button>
            <a-button @click="exportOpml">
              <template #icon><IconDownload /></template>
              下载 OPML（当前格式）
            </a-button>
            <a-button>
              <a :href="rssUrl" target="_blank" rel="noopener">新窗口打开</a>
            </a-button>
          </a-space>
        </div>
      </div>
    </a-modal>

    <!-- 明细抽屉 -->
    <a-drawer
      v-model:visible="drawerVisible"
      :width="1180"
      :title="`分类明细 · ${currentClassification?.classification_name || ''}`"
      :footer="false"
    >
      <div class="detail-two-col">
        <!-- 左列：可勾选的公众号列表 -->
        <div class="detail-col">
          <div class="detail-section-title">
            <span>添加公众号</span>
            <span class="text-muted">勾选后批量添加，输入可筛选</span>
          </div>
          <div class="detail-add">
            <a-input
              v-model="feedFilter.mpName"
              placeholder="按公众号名称筛选"
              allow-clear
              style="width: 170px"
            />
            <a-input
              v-model="feedFilter.wxsId"
              placeholder="按 wxs_id 筛选"
              allow-clear
              style="width: 170px"
            />
            <a-button type="primary" @click="submitDetailAdd">
              批量添加{{ feedSelectedKeys.length ? `(${feedSelectedKeys.length})` : '' }}
            </a-button>
          </div>

          <a-table
            :columns="feedColumns"
            :data="filteredFeeds"
            :loading="feedLoading"
            :row-selection="{ type: 'checkbox' }"
            v-model:selected-keys="feedSelectedKeys"
            :pagination="{ pageSize: 10, showTotal: true }"
            row-key="wxs_id"
          >
            <template #mp_cover="{ record }">
              <img v-if="record.mp_cover" :src="record.mp_cover" class="cell-thumb" />
              <span v-else class="cell-thumb-fallback">无图</span>
            </template>
          </a-table>
        </div>

        <!-- 右列：已添加明细 -->
        <div class="detail-col">
          <div class="detail-section-title">
            <span>已添加明细</span>
            <a-popconfirm content="确认删除选中的明细？" @ok="removeDetail">
              <a-button status="danger" size="small">删除选中</a-button>
            </a-popconfirm>
          </div>

          <a-table
            :columns="detailColumns"
            :data="detailData"
            :loading="detailLoading"
            :row-selection="{ type: 'checkbox' }"
            v-model:selected-keys="detailSelectedKeys"
            :pagination="{ pageSize: 10, showTotal: true }"
            row-key="classification_detai_id"
          >
            <template #mp_cover="{ record }">
              <img v-if="record.mp_cover" :src="record.mp_cover" class="cell-thumb" />
              <span v-else class="cell-thumb-fallback">无图</span>
            </template>
            <template #remark="{ record }">
              <span class="text-muted">{{ record.remark || '-' }}</span>
            </template>
          </a-table>
        </div>
      </div>
    </a-drawer>
  </div>
</template>

<style scoped>
/* 表格图标缩略图 */
.icon-thumb {
  width: 36px;
  height: 36px;
  object-fit: cover;
  border-radius: 8px;
  border: 1px solid var(--color-border-2, #e5e6eb);
  vertical-align: middle;
}
/* 表单上传预览 */
.icon-preview {
  display: flex;
  align-items: center;
  gap: 10px;
}
.icon-preview img {
  width: 56px;
  height: 56px;
  object-fit: cover;
  border-radius: 10px;
  border: 1px solid var(--color-border-2, #e5e6eb);
}
.icon-hint {
  font-size: 12px;
}

/* 订阅源弹窗 */
.rss-modal-body {
  padding: 4px 0 12px;
}
.rss-type-switch {
  margin-bottom: 16px;
}
.rss-hint {
  font-size: 12px;
  margin: 0 0 10px;
}
.rss-url-input {
  font-family: Consolas, 'Courier New', monospace;
  font-size: 12px;
}
.rss-actions {
  margin-top: 16px;
}

/* 明细抽屉：左右两列 */
.detail-two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  align-items: start;
}
.detail-col {
  min-width: 0;
}
.detail-section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 12px;
}
.detail-section-title .text-muted {
  font-weight: 400;
  font-size: 12px;
}
.detail-add {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
</style>
