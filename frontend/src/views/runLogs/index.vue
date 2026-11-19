<script setup>
import { reactive, ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { Message } from '@arco-design/web-vue'
import { logsApi } from '@/api/modules'

/* ======================== 运行日志（任务明细） ======================== */
// 以批次串起一次任务执行的每一步，覆盖定时任务更新 / 最新拉取 / 历史记录
const detailText = ref('')
const detailLoading = ref(false)
const detailCount = ref(0)
const detailKeep = ref(0)
const detailQuery = reactive({ taskType: '', limit: 200 })
const detailAutoRefresh = ref(false)
let detailTimer = null

// 文本框 DOM 与"自动跟随底部"状态
const detailBoxRef = ref(null)
const stickToBottom = ref(true)
let scrollBound = false

function getTextarea() {
  const inst = detailBoxRef.value
  if (!inst) return null
  if (inst.tagName === 'TEXTAREA') return inst
  return inst.$el?.querySelector('textarea') || null
}

// 用户在底部附近（<=40px）视为跟随，向上滚动离开底部则锁定位置
function onDetailScroll() {
  const ta = getTextarea()
  if (!ta) return
  const distance = ta.scrollHeight - ta.scrollTop - ta.clientHeight
  stickToBottom.value = distance <= 40
}

function bindScroll() {
  if (scrollBound) return
  const ta = getTextarea()
  if (!ta) return
  ta.addEventListener('scroll', onDetailScroll)
  scrollBound = true
}

async function scrollToBottom() {
  await nextTick()
  const ta = getTextarea()
  if (ta) {
    ta.scrollTop = ta.scrollHeight
    stickToBottom.value = true
  }
}

// 有新日志时，仅在用户未主动上滚锁定的情况下跟随到底部
watch(
  detailText,
  () => {
    if (stickToBottom.value) scrollToBottom()
  },
  { flush: 'post' },
)

onMounted(async () => {
  await nextTick()
  bindScroll()
  scrollToBottom()
})

async function loadDetailText() {
  detailLoading.value = true
  try {
    const res = await logsApi.detailText({
      taskType: detailQuery.taskType || undefined,
      limit: detailQuery.limit,
    })
    detailText.value = res?.text || '（暂无运行日志）'
    detailCount.value = res?.count || 0
    detailKeep.value = res?.limit || 0
  } finally {
    detailLoading.value = false
  }
}

function handleDetailAutoRefresh() {
  if (detailTimer) {
    clearInterval(detailTimer)
    detailTimer = null
  }
  if (detailAutoRefresh.value) {
    detailTimer = setInterval(loadDetailText, 5000)
  }
}

async function handleDetailClear() {
  await logsApi.detailClear()
  Message.success('已清空运行日志')
  loadDetailText()
}

onUnmounted(() => {
  if (detailTimer) clearInterval(detailTimer)
  const ta = getTextarea()
  if (ta && scrollBound) ta.removeEventListener('scroll', onDetailScroll)
})

loadDetailText()
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h2 class="page-title">运行日志</h2>
        <p class="page-desc">
          按批次记录任务每一步：任务发起、验证登录态、开始更新公众号、开始拉取、已拉取条数、
          无需更新、拉取出错及异常原因，方便出错回溯。当前显示 {{ detailCount }} 条，最多保留 {{ detailKeep }} 条。
        </p>
      </div>
    </div>

    <div class="table-card">
      <div class="search-bar">
        <a-form layout="inline" :model="detailQuery" @submit="loadDetailText">
          <a-form-item label="任务类型">
            <a-select
              v-model="detailQuery.taskType"
              placeholder="全部"
              allow-clear
              style="width: 130px"
              @change="loadDetailText"
            >
              <a-option value="job">定时任务</a-option>
              <a-option value="latest">最新拉取</a-option>
              <a-option value="history">历史记录</a-option>
            </a-select>
          </a-form-item>
          <a-form-item label="显示条数">
            <a-input-number
              v-model="detailQuery.limit"
              :min="1"
              :max="2000"
              style="width: 110px"
              @change="loadDetailText"
            />
          </a-form-item>
          <a-form-item label="自动刷新">
            <a-switch v-model="detailAutoRefresh" @change="handleDetailAutoRefresh" />
          </a-form-item>
          <a-form-item>
            <a-button type="primary" :loading="detailLoading" @click="loadDetailText">刷新</a-button>
            <a-button status="danger" style="margin-left: 8px" @click="handleDetailClear">清空</a-button>
          </a-form-item>
        </a-form>
      </div>
      <a-textarea
        ref="detailBoxRef"
        v-model="detailText"
        class="detail-textarea"
        rows="20"
        readonly
        placeholder="运行日志"
      />
      <div v-if="!stickToBottom" class="follow-tip">
        <a-link @click="scrollToBottom">已暂停跟随，点击回到最新日志</a-link>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 固定高度，内容超出后 textarea 自身出现滚动条 */
.detail-textarea {
  font-family: 'Cascadia Code', Consolas, 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.6;
}
.detail-textarea :deep(textarea) {
  height: 460px !important;
  min-height: 460px !important;
  resize: none;
  overflow-y: auto;
}

/* 用户上滚锁定后出现的"回到最新"提示 */
.follow-tip {
  margin-top: 8px;
  text-align: right;
}
</style>
