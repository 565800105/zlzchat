<script setup>
import { reactive, ref } from 'vue'
import { Message } from '@arco-design/web-vue'
import { jobApi } from '@/api/modules'

/* ============================ 响应式状态 ============================ */
const loading = ref(false)
const tableData = ref([])
const pagination = reactive({ total: 0, pageNum: 1, pageSize: 10 })
const query = reactive({ jobName: '' })

// 下拉选项
const classificationOptions = ref([])
const feedOptions = ref([])

// 新增/编辑弹窗
const modalVisible = ref(false)
const editing = ref(false)
const formRef = ref()
const form = reactive({
  job_id: undefined,
  job_name: '',
  cron_expression: '',
  misfire_policy: '3',
  concurrent: '1',
  status: '0',
  acount_type: '2',
  classification_id: [],
  wxs_id: [],
  remark: '',
})
const rules = {
  job_name: [{ required: true, message: '请输入任务名称' }],
  cron_expression: [{ required: true, message: '请输入 cron 表达式' }],
}

/* ============================ API 调用 ============================ */
async function loadData() {
  loading.value = true
  try {
    const res = await jobApi.list({
      pageNum: pagination.pageNum,
      pageSize: pagination.pageSize,
      jobName: query.jobName || undefined,
    })
    tableData.value = res.list || []
    pagination.total = res.total || 0
  } finally {
    loading.value = false
  }
}

async function loadOptions() {
  const [classifications, feeds] = await Promise.all([
    jobApi.classificationOptions(),
    jobApi.feedOptions(),
  ])
  classificationOptions.value = classifications || []
  feedOptions.value = feeds || []
}

/* ============================ 事件处理 ============================ */
function handleSearch() {
  pagination.pageNum = 1
  loadData()
}
function handleReset() {
  query.jobName = ''
  handleSearch()
}
function handlePageChange(page) {
  pagination.pageNum = page
  loadData()
}

function resetForm() {
  Object.assign(form, {
    job_id: undefined,
    job_name: '',
    cron_expression: '',
    misfire_policy: '3',
    concurrent: '1',
    status: '0',
    acount_type: '2',
    classification_id: [],
    wxs_id: [],
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
  // 确保多选字段为数组
  form.classification_id = Array.isArray(row.classification_id) ? [...row.classification_id] : []
  form.wxs_id = Array.isArray(row.wxs_id) ? [...row.wxs_id] : []
  modalVisible.value = true
}

async function submitForm() {
  try {
    await formRef.value?.validate()
  } catch (e) {
    return
  }
  const payload = {
    job_name: form.job_name,
    cron_expression: form.cron_expression,
    misfire_policy: form.misfire_policy,
    concurrent: form.concurrent,
    status: form.status,
    acount_type: form.acount_type,
    classification_id: form.classification_id,
    wxs_id: form.wxs_id,
    remark: form.remark,
  }
  if (editing.value) {
    payload.job_id = form.job_id
    await jobApi.edit(payload)
    Message.success('修改成功')
  } else {
    await jobApi.add(payload)
    Message.success('新增成功')
  }
  modalVisible.value = false
  loadData()
}

async function removeRow(row) {
  await jobApi.remove([row.job_id])
  Message.success('删除成功')
  loadData()
}

async function handleRun(row) {
  await jobApi.run(row.job_id)
  Message.success('已触发执行')
}

async function handleToggle(row) {
  const res = await jobApi.toggle(row.job_id)
  Message.success(res?.msg || '状态已切换')
  loadData()
}

/* ============================ 表格列 ============================ */
const columns = [
  { title: '任务ID', dataIndex: 'job_id', width: 80 },
  { title: '任务名称', dataIndex: 'job_name', width: 150 },
  { title: 'cron表达式', dataIndex: 'cron_expression', width: 130 },
  { title: '状态', dataIndex: 'status', slotName: 'status', width: 90 },
  { title: '账号策略', dataIndex: 'acount_type', slotName: 'acount_type', width: 100 },
  { title: '执行策略', dataIndex: 'misfire_policy', slotName: 'misfire_policy', width: 100 },
  { title: '并发', dataIndex: 'concurrent', slotName: 'concurrent', width: 80 },
  { title: '备注', dataIndex: 'remark', ellipsis: true },
  { title: '操作', dataIndex: 'actions', slotName: 'actions', width: 200, fixed: 'right' },
]

loadData()
loadOptions()
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h2 class="page-title">定时任务配置</h2>
        <p class="page-desc">配置定时更新任务的执行计划与公众号范围</p>
      </div>
      <a-button type="primary" @click="openAdd">+ 新增任务</a-button>
    </div>

    <!-- 搜索栏 -->
    <div class="search-bar">
      <a-form layout="inline" :model="query" @submit="handleSearch">
        <a-form-item label="任务名称">
          <a-input v-model="query.jobName" placeholder="任务名称" allow-clear @press-enter="handleSearch" />
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
        row-key="job_id"
        :scroll="{ x: 1500 }"
        @page-change="handlePageChange"
      >
        <template #status="{ record }">
          <a-tag :color="record.status === '0' ? 'green' : 'gray'">
            {{ record.status === '0' ? '正常' : '暂停' }}
          </a-tag>
        </template>
        <template #acount_type="{ record }">
          <a-tag color="arcoblue">{{ record.acount_type === '1' ? '异常切换' : '轮询' }}</a-tag>
        </template>
        <template #misfire_policy="{ record }">
          <span>{{ { 1: '立即执行', 2: '执行一次', 3: '放弃执行' }[record.misfire_policy] || '-' }}</span>
        </template>
        <template #concurrent="{ record }">
          <span>{{ record.concurrent === '0' ? '允许' : '禁止' }}</span>
        </template>
        <template #actions="{ record }">
          <a-space>
            <a-button type="text" size="small" @click="handleRun(record)">立即执行</a-button>
            <a-button type="text" size="small" @click="handleToggle(record)">
              {{ record.status === '0' ? '暂停' : '恢复' }}
            </a-button>
            <a-button type="text" size="small" @click="openEdit(record)">编辑</a-button>
            <a-popconfirm content="确认删除该任务？" @ok="removeRow(record)">
              <a-button type="text" size="small" status="danger">删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </a-table>
    </div>

    <!-- 新增/编辑弹窗 -->
    <a-modal
      v-model:visible="modalVisible"
      :title="editing ? '编辑定时任务' : '新增定时任务'"
      :width="680"
      @ok="submitForm"
      @cancel="modalVisible = false"
    >
      <a-form ref="formRef" :model="form" :rules="rules" layout="vertical">
        <a-form-item field="job_name" label="任务名称">
          <a-input v-model="form.job_name" placeholder="请输入任务名称" />
        </a-form-item>

        <a-form-item field="cron_expression" label="cron表达式" help="格式：秒 分 时 日 月 周">
          <a-input v-model="form.cron_expression" placeholder="例如：0 0/5 * * * ?" />
        </a-form-item>

        <a-form-item label="执行策略" field="misfire_policy">
          <a-radio-group v-model="form.misfire_policy">
            <a-radio value="1">立即执行</a-radio>
            <a-radio value="2">执行一次</a-radio>
            <a-radio value="3">放弃执行</a-radio>
          </a-radio-group>
        </a-form-item>

        <a-form-item label="并发执行" field="concurrent">
          <a-radio-group v-model="form.concurrent">
            <a-radio value="0">允许</a-radio>
            <a-radio value="1">禁止</a-radio>
          </a-radio-group>
        </a-form-item>

        <a-form-item label="状态" field="status">
          <a-radio-group v-model="form.status">
            <a-radio value="0">正常</a-radio>
            <a-radio value="1">暂停</a-radio>
          </a-radio-group>
        </a-form-item>

        <a-form-item label="账号策略" field="acount_type">
          <a-radio-group v-model="form.acount_type">
            <a-radio value="1">异常切换</a-radio>
            <a-radio value="2">轮询</a-radio>
          </a-radio-group>
        </a-form-item>

        <a-form-item label="分组" field="classification_id">
          <a-select
            v-model="form.classification_id"
            multiple
            placeholder="请选择分组（可多选）"
            allow-clear
          >
            <a-option v-for="o in classificationOptions" :key="o.value" :value="o.value">
              {{ o.label }}
            </a-option>
          </a-select>
        </a-form-item>

        <a-form-item label="公众号" field="wxs_id">
          <a-select v-model="form.wxs_id" multiple placeholder="请选择公众号（可多选）" allow-clear>
            <a-option v-for="o in feedOptions" :key="o.value" :value="o.value">
              {{ o.label }}
            </a-option>
          </a-select>
        </a-form-item>

        <a-form-item label="备注" field="remark">
          <a-textarea v-model="form.remark" placeholder="备注" :rows="3" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>
