<script setup>
import { reactive, ref } from 'vue'
import { updateLogApi } from '@/api/modules'

/* ============================ 响应式状态 ============================ */
const loading = ref(false)
const tableData = ref([])
const pagination = reactive({ total: 0, pageNum: 1, pageSize: 10 })
const query = reactive({
  feedName: '',
  logCatagory: '',
  logSta: '',
  logResultSta: '',
})

const categoryOptions = [
  { label: '定时任务', value: '1' },
  { label: '最新同步', value: '2' },
  { label: '历史更新', value: '3' },
]
const staOptions = [
  { label: '执行中', value: '1' },
  { label: '执行结束', value: '2' },
]
const resultOptions = [
  { label: '正常', value: '1' },
  { label: '异常', value: '2' },
]

/* ============================ API 调用 ============================ */
async function loadData() {
  loading.value = true
  try {
    const res = await updateLogApi.list({
      pageNum: pagination.pageNum,
      pageSize: pagination.pageSize,
      feedName: query.feedName || undefined,
      logCatagory: query.logCatagory || undefined,
      logSta: query.logSta || undefined,
      logResultSta: query.logResultSta || undefined,
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
  Object.assign(query, { feedName: '', logCatagory: '', logSta: '', logResultSta: '' })
  handleSearch()
}

function handlePageChange(page) {
  pagination.pageNum = page
  loadData()
}

function staColor(value) {
  return value === '1' ? 'blue' : 'green'
}
function resultColor(value) {
  return value === '1' ? 'green' : 'red'
}
function categoryColor(value) {
  return { 1: 'purple', 2: 'cyan', 3: 'orange' }[value] || 'gray'
}

/* ============================ 表格列 ============================ */
const columns = [
  { title: '公众号', dataIndex: 'feed_name', width: 150 },
  { title: '类别', dataIndex: 'log_catagory', slotName: 'log_catagory', width: 110 },
  { title: '状态', dataIndex: 'log_sta', slotName: 'log_sta', width: 100 },
  { title: '结果', dataIndex: 'log_result_sta', slotName: 'log_result_sta', width: 100 },
  { title: '更新数量', dataIndex: 'update_num', width: 100 },
  { title: '历史起止', dataIndex: 'history_range', slotName: 'history_range', width: 140 },
  { title: '异常原因', dataIndex: 'remark', slotName: 'remark', ellipsis: true },
  { title: '创建时间', dataIndex: 'create_time', slotName: 'create_time', width: 170 },
]

loadData()
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h2 class="page-title">更新记录</h2>
        <p class="page-desc">查看公众号内容的同步与更新历史</p>
      </div>
    </div>

    <!-- 搜索栏 -->
    <div class="search-bar">
      <a-form layout="inline" :model="query" @submit="handleSearch">
        <a-form-item label="公众号">
          <a-input v-model="query.feedName" placeholder="公众号名称" allow-clear />
        </a-form-item>
        <a-form-item label="类别">
          <a-select v-model="query.logCatagory" placeholder="全部" allow-clear style="width: 130px">
            <a-option v-for="o in categoryOptions" :key="o.value" :value="o.value">{{ o.label }}</a-option>
          </a-select>
        </a-form-item>
        <a-form-item label="状态">
          <a-select v-model="query.logSta" placeholder="全部" allow-clear style="width: 120px">
            <a-option v-for="o in staOptions" :key="o.value" :value="o.value">{{ o.label }}</a-option>
          </a-select>
        </a-form-item>
        <a-form-item label="结果">
          <a-select v-model="query.logResultSta" placeholder="全部" allow-clear style="width: 110px">
            <a-option v-for="o in resultOptions" :key="o.value" :value="o.value">{{ o.label }}</a-option>
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
        row-key="log_id"
        :scroll="{ x: 1100 }"
        @page-change="handlePageChange"
      >
        <template #log_catagory="{ record }">
          <a-tag :color="categoryColor(record.log_catagory)">
            {{ { 1: '定时任务', 2: '最新同步', 3: '历史更新' }[record.log_catagory] || '-' }}
          </a-tag>
        </template>
        <template #log_sta="{ record }">
          <a-tag :color="staColor(record.log_sta)">
            {{ record.log_sta === '1' ? '执行中' : '执行结束' }}
          </a-tag>
        </template>
        <template #log_result_sta="{ record }">
          <a-tag :color="resultColor(record.log_result_sta)">
            {{ record.log_result_sta === '1' ? '正常' : '异常' }}
          </a-tag>
        </template>
        <template #history_range="{ record }">
          <span class="text-muted">{{ record.history_start_num ?? '-' }} ~ {{ record.history_end_num ?? '-' }}</span>
        </template>
        <template #remark="{ record }">
          <span :class="record.log_result_sta === '2' ? 'text-danger' : 'text-muted'">
            {{ record.remark || '-' }}
          </span>
        </template>
        <template #create_time="{ record }">
          <span class="text-muted">{{ record.create_time }}</span>
        </template>
      </a-table>
    </div>
  </div>
</template>
