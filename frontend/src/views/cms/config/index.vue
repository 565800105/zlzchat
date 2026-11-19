<script setup>
import { reactive, ref } from 'vue'
import { Message } from '@arco-design/web-vue'
import { configApi } from '@/api/modules'

/* ============================ 响应式状态 ============================ */
const loading = ref(false)
const saving = ref(false)
const tableData = ref([])
// 行内编辑的草稿值：以 config_key 为键
const draftValues = reactive({})

// config_key → 友好中文名称
const FRIENDLY_NAMES = {
  'api.checkFeedUpdate': '检测公众号是否更新',
  'api.updateFeedTime': '更新间隔时间(秒)',
  'api.feishuSecret': '飞书机器人秘钥',
  'api.feishuUrl': '飞书机器人Url',
  'api.apiKey': '请求key',
  'api.dingdingSecret': '钉钉机器人秘钥',
  'api.dingdingToken': '钉钉机器人Token',
  'api.articlecont': '是否全文抓取',
  'api.serverUrl': '外部中转服务地址',
  'api.publicUrl': '服务器对外域名/IP',
  'rss.count': '订阅源显示多条',
  'rss.name': '订阅源名称',
  'api.middlewareKey': '中转服务通讯key',
}

// 不允许修改的配置键（与后端 READONLY_CONFIG_KEYS 对应）
const READONLY_KEYS = ['api.middlewareKey']
function isReadonly(row) {
  return READONLY_KEYS.includes(row.config_key)
}

// 配置说明：几个固定项用内置说明（后端也会同步 remark），其余用库里的 remark
const FIXED_REMARKS = {
  'api.middlewareKey': '中转服务通讯key，系统内置，不允许修改',
  'api.apiKey': '服务提供api鉴权key',
  'api.serverUrl': '登录态续期服务地址',
  'api.publicUrl': '服务器对外域名/IP，用于订阅源中图片等资源地址',
}
function remarkText(row) {
  return FIXED_REMARKS[row.config_key] || row.remark || '-'
}

/* ============================ API 调用 ============================ */
async function loadData() {
  loading.value = true
  try {
    const res = await configApi.list()
    tableData.value = res || []
    // 初始化草稿
    tableData.value.forEach((row) => {
      draftValues[row.config_key] = row.config_value ?? ''
    })
  } finally {
    loading.value = false
  }
}

/* ============================ 事件处理 ============================ */
function friendlyName(row) {
  return FRIENDLY_NAMES[row.config_key] || row.config_name || row.config_key
}

async function saveRow(row) {
  if (isReadonly(row)) {
    Message.warning('该配置为系统内置通讯key，不允许修改')
    return
  }
  await configApi.edit({
    config_id: row.config_id,
    config_value: draftValues[row.config_key],
    config_name: row.config_name,
    remark: row.remark,
  })
  Message.success('保存成功')
  row.config_value = draftValues[row.config_key]
}

async function saveAll() {
  const values = {}
  tableData.value.forEach((row) => {
    if (isReadonly(row)) return // 只读项不参与批量保存
    values[row.config_key] = draftValues[row.config_key]
  })
  saving.value = true
  try {
    await configApi.batch(values)
    Message.success('批量保存成功')
    await loadData()
  } finally {
    saving.value = false
  }
}

/* ============================ 表格列 ============================ */
const columns = [
  { title: '配置名称', dataIndex: 'config_name', slotName: 'config_name', width: 220 },
  { title: '配置键', dataIndex: 'config_key', slotName: 'config_key', width: 200 },
  { title: '配置值', dataIndex: 'config_value', slotName: 'config_value' },
  { title: '说明', dataIndex: 'remark', slotName: 'remark', width: 220 },
  { title: '更新时间', dataIndex: 'update_time', slotName: 'update_time', width: 170 },
  { title: '操作', dataIndex: 'actions', slotName: 'actions', width: 90, fixed: 'right' },
]

loadData()
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h2 class="page-title">配置项管理</h2>
        <p class="page-desc">管理系统运行参数（api.* / rss.* 配置），支持行内编辑与批量保存</p>
      </div>
      <a-button type="primary" :loading="saving" @click="saveAll">批量保存</a-button>
    </div>

    <div class="table-card">
      <a-table
        :columns="columns"
        :data="tableData"
        :loading="loading"
        :pagination="false"
        row-key="config_id"
        :scroll="{ x: 1000 }"
      >
        <template #config_name="{ record }">
          <span class="config-name">{{ friendlyName(record) }}</span>
        </template>
        <template #config_key="{ record }">
          <span class="mono">{{ record.config_key }}</span>
        </template>
        <template #config_value="{ record }">
          <a-input
            v-model="draftValues[record.config_key]"
            placeholder="配置值"
            size="small"
            :disabled="isReadonly(record)"
          />
        </template>
        <template #remark="{ record }">
          <span :class="isReadonly(record) ? 'readonly-hint' : 'text-muted'">
            {{ remarkText(record) }}
          </span>
        </template>
        <template #update_time="{ record }">
          <span class="text-muted">{{ record.update_time || '-' }}</span>
        </template>
        <template #actions="{ record }">
          <a-button v-if="!isReadonly(record)" type="text" size="small" @click="saveRow(record)">保存</a-button>
          <a-tag v-else color="gray">只读</a-tag>
        </template>
      </a-table>
    </div>
  </div>
</template>

<style scoped>
.config-name {
  font-weight: 600;
  color: var(--app-text);
}
.readonly-hint {
  color: var(--color-text-4, #86909c);
  font-size: 12px;
}
</style>
