<script setup>
import { reactive, ref, onUnmounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import { accountsApi } from '@/api/modules'

/* ============================ 响应式状态 ============================ */
const loading = ref(false)
const tableData = ref([])
const pagination = reactive({ total: 0, pageNum: 1, pageSize: 10 })
const query = reactive({ status: undefined })

// 扫码弹窗
const qrVisible = ref(false)
const qrLoading = ref(false)
const qrUrl = ref('')
const qrUid = ref('')
const qrInstallId = ref('')
const qrScanning = ref(false)
let pollTimer = null

/* ============================ API 调用 ============================ */
async function loadData() {
  loading.value = true
  try {
    const res = await accountsApi.list({
      pageNum: pagination.pageNum,
      pageSize: pagination.pageSize,
      status: query.status,
    })
    tableData.value = res.list || []
    pagination.total = res.total || 0
  } finally {
    loading.value = false
  }
}

/* ============================ 事件处理 ============================ */
function handleSearch() {
  pagination.pageNum = 1
  loadData()
}
function handleReset() {
  query.status = undefined
  handleSearch()
}
function handlePageChange(page) {
  pagination.pageNum = page
  loadData()
}

function statusColor(value) {
  return { 1: 'green', 2: 'gray', 3: 'red' }[value] || 'gray'
}
function statusText(value) {
  return { 1: '正常', 2: '禁用', 3: '风控' }[value] || '-'
}

async function removeRow(row) {
  await accountsApi.remove([row.accounts_id])
  Message.success('删除成功')
  loadData()
}

/* ---------------- 扫码登录 ---------------- */
async function openQrcode() {
  qrVisible.value = true
  qrScanning.value = false
  qrUrl.value = ''
  await fetchQrcode()
}

async function fetchQrcode() {
  qrLoading.value = true
  try {
    const data = await accountsApi.qrcode()
    qrUrl.value = data?.url || ''
    qrUid.value = data?.uid || ''
    qrInstallId.value = data?.installId || ''
    qrScanning.value = true
    startPoll()
  } catch (e) {
    qrScanning.value = false
  } finally {
    qrLoading.value = false
  }
}

function startPoll() {
  stopPoll()
  let attempts = 0
  const MAX_ATTEMPTS = 90 // 最多轮询约 3 分钟，防止无限轮询
  // 每 2 秒轮询一次扫码回调，只有明确拿到 success=true 才停止
  pollTimer = setInterval(async () => {
    if (!qrScanning.value) {
      stopPoll()
      return
    }
    attempts += 1
    if (attempts > MAX_ATTEMPTS) {
      stopPoll()
      qrScanning.value = false
      Message.warning('扫码超时，请刷新二维码重试')
      return
    }
    try {
      const result = await accountsApi.qrcodeCheck(qrUid.value, qrInstallId.value)
      // 后端以 data.success 明确标识是否扫码成功
      if (result && result.success === true) {
        stopPoll()
        qrScanning.value = false
        qrVisible.value = false
        Message.success(`扫码添加成功${result.nickName ? `（${result.nickName}）` : ''}`)
        loadData()
      }
      // success=false：尚未扫码，继续轮询
    } catch (e) {
      // 网络/服务异常：继续轮询，由次数上限兜底
    }
  }, 2000)
}

function stopPoll() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function handleQrCancel() {
  stopPoll()
  qrScanning.value = false
  qrVisible.value = false
}

onUnmounted(stopPoll)

/* ============================ 表格列 ============================ */
const columns = [
  { title: '昵称', dataIndex: 'nick_name', width: 160 },
  { title: '平台', dataIndex: 'category', slotName: 'category', width: 100 },
  { title: '状态', dataIndex: 'status', slotName: 'status', width: 100 },
  { title: '备注', dataIndex: 'remark', ellipsis: true },
  { title: '创建时间', dataIndex: 'create_time', slotName: 'create_time', width: 170 },
  { title: '操作', dataIndex: 'actions', slotName: 'actions', width: 140, fixed: 'right' },
]

loadData()
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h2 class="page-title">账号配置</h2>
        <p class="page-desc">微信读书账号通过扫码登录添加，扫码后自动采集登录态</p>
      </div>
      <a-button type="primary" @click="openQrcode">+ 扫码添加账号</a-button>
    </div>

    <!-- 搜索栏 -->
    <div class="search-bar">
      <a-form layout="inline" :model="query" @submit="handleSearch">
        <a-form-item label="状态">
          <a-select v-model="query.status" placeholder="全部" allow-clear style="width: 120px">
            <a-option :value="1">正常</a-option>
            <a-option :value="2">禁用</a-option>
            <a-option :value="3">风控</a-option>
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
        row-key="accounts_id"
        :scroll="{ x: 1000 }"
        @page-change="handlePageChange"
      >
        <template #category>
          <a-tag color="green">微信读书</a-tag>
        </template>
        <template #status="{ record }">
          <a-tag :color="statusColor(record.status)">{{ statusText(record.status) }}</a-tag>
        </template>
        <template #create_time="{ record }">
          <span class="text-muted">{{ record.create_time }}</span>
        </template>
        <template #actions="{ record }">
          <a-popconfirm content="确认删除该账号？" @ok="removeRow(record)">
            <a-button type="text" size="small" status="danger">删除</a-button>
          </a-popconfirm>
        </template>
      </a-table>
    </div>

    <!-- 扫码弹窗 -->
    <a-modal
      v-model:visible="qrVisible"
      title="微信读书扫码登录"
      :width="420"
      :footer="false"
      @cancel="handleQrCancel"
    >
      <div class="qr-box">
        <a-spin :loading="qrLoading" style="width: 100%">
          <div class="qr-image-wrap">
            <img v-if="qrUrl" :src="qrUrl" alt="登录二维码" class="qr-image" />
            <div v-else class="qr-placeholder">二维码加载中...</div>
          </div>
        </a-spin>
        <div class="qr-tip">
          <p>请使用 <b>微信</b> 扫描二维码登录微信读书</p>
          <p class="qr-tip-sub">
            <a-tag v-if="qrScanning" color="arcoblue">等待扫码...</a-tag>
            <span v-else>请点击下方「刷新二维码」重试</span>
          </p>
        </div>
        <a-button long @click="fetchQrcode">刷新二维码</a-button>
      </div>
    </a-modal>
  </div>
</template>

<style scoped>
.qr-box {
  text-align: center;
  padding: 8px 0;
}
.qr-image-wrap {
  width: 220px;
  height: 220px;
  margin: 0 auto 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px dashed var(--color-border-2);
  border-radius: 8px;
  background: #fafafa;
}
.qr-image {
  width: 200px;
  height: 200px;
}
.qr-placeholder {
  color: var(--color-text-3);
  font-size: 14px;
}
.qr-tip {
  margin-bottom: 16px;
  color: var(--color-text-2);
}
.qr-tip p {
  margin: 6px 0;
}
.qr-tip-sub {
  font-size: 13px;
  color: var(--color-text-3);
}
</style>
