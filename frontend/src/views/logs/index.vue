<script setup>
import { reactive, ref } from 'vue'
import { logsApi } from '@/api/modules'

/* ============================ 响应式状态 ============================ */
const loading = ref(false)
const tableData = ref([])
const stats = ref({ total: 0, failed: 0, keepRecent: 100 })
const query = reactive({
  logType: '',
  onlyFailed: false,
  limit: 100,
})

/* ============================ API 调用 ============================ */
async function loadData() {
  loading.value = true
  try {
    tableData.value =
      (await logsApi.list({
        logType: query.logType || undefined,
        limit: query.limit,
        onlyFailed: query.onlyFailed,
      })) || []
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  stats.value = (await logsApi.stats()) || stats.value
}

/* ============================ 事件处理 ============================ */
function handleSearch() {
  loadData()
}
function handleReset() {
  Object.assign(query, { logType: '', onlyFailed: false, limit: 100 })
  loadData()
}
function handleSwitchChange() {
  loadData()
}

function logTypeColor(type) {
  return { request: 'arcoblue', job: 'purple', login: 'green' }[type] || 'gray'
}
function logTypeText(type) {
  return { request: '请求', job: '任务', login: '登录' }[type] || type || '-'
}

/* ============================ 表格列 ============================ */
const columns = [
  { title: '类型', dataIndex: 'log_type', slotName: 'log_type', width: 90 },
  { title: '方法', dataIndex: 'method', width: 80 },
  { title: '路径', dataIndex: 'url', width: 180, ellipsis: true },
  { title: '描述', dataIndex: 'description', width: 130, ellipsis: true },
  { title: '操作人', dataIndex: 'user_name', width: 110 },
  { title: 'IP', dataIndex: 'ip', width: 130 },
  { title: '状态码', dataIndex: 'status_code', width: 90 },
  { title: '结果', dataIndex: 'success', slotName: 'success', width: 90 },
  { title: '异常原因', dataIndex: 'error_msg', slotName: 'error_msg', ellipsis: true },
  { title: '耗时(ms)', dataIndex: 'cost_time', width: 100 },
  { title: '时间', dataIndex: 'create_time', slotName: 'create_time', width: 170 },
]

loadData()
loadStats()
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h2 class="page-title">请求日志</h2>
        <p class="page-desc">查看最新的请求、任务与登录日志，支持异常筛选</p>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stat-grid">
      <div class="stat-card">
        <div class="stat-icon blue">Σ</div>
        <div>
          <div class="stat-value">{{ stats.total }}</div>
          <div class="stat-label">日志总数</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon red">!</div>
        <div>
          <div class="stat-value">{{ stats.failed }}</div>
          <div class="stat-label">异常日志</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon orange">↺</div>
        <div>
          <div class="stat-value">{{ stats.keepRecent }}</div>
          <div class="stat-label">保留最近条数</div>
        </div>
      </div>
    </div>

    <!-- 筛选栏 -->
    <div class="search-bar">
      <a-form layout="inline" :model="query" @submit="handleSearch">
        <a-form-item label="日志类型">
          <a-select v-model="query.logType" placeholder="全部" allow-clear style="width: 130px">
            <a-option value="request">请求</a-option>
            <a-option value="job">任务</a-option>
            <a-option value="login">登录</a-option>
          </a-select>
        </a-form-item>
        <a-form-item label="只看异常">
          <a-switch v-model="query.onlyFailed" @change="handleSwitchChange" />
        </a-form-item>
        <a-form-item label="显示条数">
          <a-input-number v-model="query.limit" :min="1" :max="200" style="width: 110px" />
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
        :pagination="{ pageSize: 20, showTotal: true }"
        row-key="id"
        :scroll="{ x: 1500 }"
      >
        <template #log_type="{ record }">
          <a-tag :color="logTypeColor(record.log_type)">{{ logTypeText(record.log_type) }}</a-tag>
        </template>
        <template #success="{ record }">
          <a-tag :color="record.success ? 'green' : 'red'">
            {{ record.success ? '成功' : '失败' }}
          </a-tag>
        </template>
        <template #error_msg="{ record }">
          <span :class="record.error_msg ? 'text-danger' : 'text-muted'">
            {{ record.error_msg || '-' }}
          </span>
        </template>
        <template #create_time="{ record }">
          <span class="text-muted">{{ record.create_time }}</span>
        </template>
      </a-table>
    </div>
  </div>
</template>
