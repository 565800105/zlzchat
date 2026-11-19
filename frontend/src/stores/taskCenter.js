import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { articlesApi } from '@/api/modules'

const STORAGE_KEY = 'zlzchat_task_center'
const MAX_TASKS = 100

function loadTasks() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch (e) {
    return []
  }
}

/**
 * 任务中心：记录「最新同步 / 历史同步」任务状态，右下角悬浮面板展示。
 * - 任务在后端执行，前端刷新不影响其运行；task.backendId 用于刷新后查询后端真实结果。
 * - 列表持久化到 localStorage，刷新不丢。
 */
export const useTaskCenter = defineStore('taskCenter', () => {
  const restored = loadTasks()
  const tasks = ref(restored)
  const panelVisible = ref(false)
  let seq = restored.reduce((max, t) => Math.max(max, Number(t.id) || 0), 0)

  const runningCount = computed(() => tasks.value.filter((t) => t.status === 'running').length)
  const hasRunning = computed(() => runningCount.value > 0)

  watch(
    tasks,
    (val) => {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(val.slice(0, MAX_TASKS)))
      } catch (e) {
        // 存储不可用时忽略
      }
    },
    { deep: true },
  )

  /**
   * 登记任务。返回 { id, backendId }：
   * - id 前端内部标识
   * - backendId 传给后端，刷新后据此查询真实结果
   */
  function start({ title, detail = '' }) {
    const id = ++seq
    const backendId = `task_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
    tasks.value.unshift({
      id,
      backendId,
      title,
      detail,
      status: 'running',
      startTime: Date.now(),
      endTime: null,
      msg: '',
      updateNum: 0,
    })
    return { id, backendId }
  }

  /** 结束任务（前端已拿到结果时调用） */
  function finish(id, { status = 'success', msg = '', updateNum = 0 } = {}) {
    const task = tasks.value.find((t) => t.id === id)
    if (!task) return
    task.status = status
    task.msg = msg || (status === 'success' ? '执行完成' : '执行失败')
    task.updateNum = updateNum
    task.endTime = Date.now()
  }

  /** 刷新后：向后端查询仍未完成任务的真实状态 */
  async function syncFromBackend() {
    const pending = tasks.value.filter((t) => t.status === 'running' && t.backendId)
    if (!pending.length) return
    await Promise.all(
      pending.map(async (task) => {
        try {
          const st = await articlesApi.taskStatus(task.backendId)
          if (st && st.status && st.status !== 'running') {
            task.status = st.status
            task.updateNum = st.updateNum || 0
            task.msg =
              st.status === 'success'
                ? `已新增 ${st.updateNum || 0} 条 · 后台执行完成`
                : st.msg || '执行失败'
            task.endTime = st.endTime || Date.now()
          }
        } catch (e) {
          // 查询失败保留原状态，下次刷新再试
        }
      }),
    )
  }

  function remove(id) {
    tasks.value = tasks.value.filter((t) => t.id !== id)
  }

  function clearFinished() {
    tasks.value = tasks.value.filter((t) => t.status === 'running')
  }

  function togglePanel() {
    panelVisible.value = !panelVisible.value
  }

  return {
    tasks,
    panelVisible,
    runningCount,
    hasRunning,
    start,
    finish,
    syncFromBackend,
    remove,
    clearFinished,
    togglePanel,
  }
})
