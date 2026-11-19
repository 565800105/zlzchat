<script setup>
import { computed, ref, reactive, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { IconGift } from '@arco-design/web-vue/es/icon'
import { useUserStore } from '@/stores/user'
import { authApi } from '@/api/modules'
import {
  IconMenuFold,
  IconMenuUnfold,
  IconApps,
  IconSync,
  IconBook,
  IconFile,
  IconUser,
  IconSettings,
  IconClockCircle,
  IconList,
  IconExport,
  IconDashboard,
  IconMore,
  IconCode,
  IconLoading,
  IconCheckCircle,
  IconCloseCircle,
  IconClose,
  IconNotification,
} from '@arco-design/web-vue/es/icon'
import { useTaskCenter } from '@/stores/taskCenter'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const taskCenter = useTaskCenter()

// 任务状态文本 / 颜色
function taskStatusText(status) {
  return { running: '执行中', success: '成功', error: '失败' }[status] || status
}
function taskStatusColor(status) {
  return { running: 'arcoblue', success: 'green', error: 'red' }[status] || 'gray'
}
function formatTaskTime(ts) {
  if (!ts) return '-'
  const d = new Date(ts)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`
}

// 侧边栏折叠状态
const collapsed = ref(false)
const openKeys = ref(['monitor', 'wechat'])

// 当前选中的菜单项
const selectedKeys = computed(() => [route.name])

// 当前页面标题
const pageTitle = computed(() => route.meta.title || '控制台')

// 用户名：优先显示昵称
const displayName = computed(
  () => userStore.userInfo?.nickName || userStore.userInfo?.userName || '管理员',
)

/** 菜单点击：按路由 name 跳转 */
function handleMenuClick(key) {
  router.push({ name: key })
}

/* ============ 赞赏码弹窗 ============ */
const rewardVisible = ref(false)
const REWARD_ON_LOGIN_KEY = 'zlzchat_reward_on_login'
const REWARD_IMG = '/reward.png'
const GITHUB_URL = 'https://github.com/565800105/zlzchat'

function openReward() {
  rewardVisible.value = true
}

// 后台任务状态轮询：仅在有运行中任务时查询，全部完成则空闲（避免无效请求）
let taskPollTimer = null
const TASK_POLL_INTERVAL = 3000
let taskPollingInFlight = false

async function pollTaskStatus() {
  if (taskPollingInFlight) return
  if (!taskCenter.hasRunning) return // 无运行中任务，跳过
  taskPollingInFlight = true
  try {
    await taskCenter.syncFromBackend()
  } finally {
    taskPollingInFlight = false
  }
}

onMounted(() => {
  // 每次登录成功后弹出赞赏码一次；标记用完即清，刷新页面不会重复弹
  if (sessionStorage.getItem(REWARD_ON_LOGIN_KEY)) {
    rewardVisible.value = true
    sessionStorage.removeItem(REWARD_ON_LOGIN_KEY)
  }
  // 立即查一次 + 启动轮询，后台任务完成会自动更新，无需手动刷新
  pollTaskStatus()
  taskPollTimer = setInterval(pollTaskStatus, TASK_POLL_INTERVAL)
})

onUnmounted(() => {
  if (taskPollTimer) {
    clearInterval(taskPollTimer)
    taskPollTimer = null
  }
})

/* ============ 修改密码 ============ */
const PWD_CHANGED_KEY = 'zlzchat_password_changed'
const pwdVisible = ref(false)
const pwdSaving = ref(false)
const pwdFormRef = ref()
const pwdForm = reactive({ oldPassword: '', newPassword: '', confirmPassword: '' })
const pwdRules = {
  oldPassword: [{ required: true, message: '请输入原密码' }],
  newPassword: [
    { required: true, message: '请输入新密码' },
    { minLength: 6, message: '新密码至少 6 位' },
  ],
  confirmPassword: [
    { required: true, message: '请再次输入新密码' },
    {
      validator: (value, callback) => {
        if (value !== pwdForm.newPassword) callback('两次输入的密码不一致')
        else callback()
      },
    },
  ],
}

function openPassword() {
  pwdForm.oldPassword = ''
  pwdForm.newPassword = ''
  pwdForm.confirmPassword = ''
  pwdVisible.value = true
}

async function submitPassword() {
  try {
    await pwdFormRef.value?.validate()
  } catch (e) {
    return
  }
  pwdSaving.value = true
  try {
    await authApi.changePassword({
      old_password: pwdForm.oldPassword,
      new_password: pwdForm.newPassword,
    })
    Message.success('密码修改成功，请重新登录')
    localStorage.setItem(PWD_CHANGED_KEY, '1') // 登录页据此不再预填默认密码
    pwdVisible.value = false
    await userStore.logout()
    router.push('/login')
  } catch (e) {
    // 错误信息由拦截器统一提示
  } finally {
    pwdSaving.value = false
  }
}

/** 退出登录 */
async function handleLogout() {
  await userStore.logout()
  Message.success('已退出登录')
  router.push('/login')
}
</script>

<template>
  <a-layout class="app-layout">
    <!-- ============ 侧边栏 ============ -->
    <a-layout-sider
      v-model:collapsed="collapsed"
      :width="228"
      :collapsed-width="64"
      class="app-sider"
      collapsible
      :trigger="null"
    >
      <!-- 顶部微光装饰 -->
      <div class="sider-glow"></div>

      <!-- 品牌 Logo -->
      <div class="logo" :class="{ 'logo--collapsed': collapsed }">
        <div class="logo-mark">
          <span>Z</span>
        </div>
        <div v-if="!collapsed" class="logo-text">
          <strong>ZLZCHAT</strong>
          <small>公众号信息管理平台</small>
        </div>
      </div>

      <!-- 菜单 -->
      <a-menu
        mode="vertical"
        theme="dark"
        :selected-keys="selectedKeys"
        :open-keys="openKeys"
        class="app-menu"
        @menu-item-click="handleMenuClick"
        @update:open-keys="openKeys = $event"
      >
        <a-sub-menu key="monitor">
          <template #icon><IconDashboard /></template>
          <template #title>系统</template>
          <a-menu-item key="job">
            <template #icon><IconClockCircle /></template>
            定时任务
          </a-menu-item>
          <a-menu-item key="logs">
            <template #icon><IconList /></template>
            请求日志
          </a-menu-item>
          <a-menu-item key="runLogs">
            <template #icon><IconCode /></template>
            运行日志
          </a-menu-item>
          <a-menu-item key="config">
            <template #icon><IconSettings /></template>
            配置项
          </a-menu-item>
        </a-sub-menu>

        <a-sub-menu key="wechat">
          <template #icon><IconApps /></template>
          <template #title>公众号</template>
          <a-menu-item key="accounts">
            <template #icon><IconUser /></template>
            账号配置
          </a-menu-item>
          <a-menu-item key="feeds">
            <template #icon><IconBook /></template>
            公众号信息
          </a-menu-item>
          <a-menu-item key="classification">
            <template #icon><IconApps /></template>
            订阅源分类
          </a-menu-item>
          <a-menu-item key="mparticles">
            <template #icon><IconFile /></template>
            文章信息
          </a-menu-item>
          <a-menu-item key="updateLog">
            <template #icon><IconSync /></template>
            更新记录
          </a-menu-item>
        </a-sub-menu>
      </a-menu>

      <!-- 侧边栏底部状态 -->
      <div v-if="!collapsed" class="sider-footer">
        <span class="status-dot"></span>
        <span>系统运行中</span>
        <IconMore class="footer-more" />
      </div>
    </a-layout-sider>

    <a-layout class="app-main">
      <!-- ============ 顶部栏 ============ -->
      <a-layout-header class="app-header">
        <div class="header-left">
          <button class="collapse-btn" @click="collapsed = !collapsed" aria-label="折叠菜单">
            <IconMenuUnfold v-if="collapsed" />
            <IconMenuFold v-else />
          </button>
          <a-breadcrumb class="header-crumb">
            <a-breadcrumb-item>zlzchat</a-breadcrumb-item>
            <a-breadcrumb-item>{{ pageTitle }}</a-breadcrumb-item>
          </a-breadcrumb>
        </div>

        <div class="header-right">
          <span class="reward-entry" @click="openReward">
            <IconGift />
            赞赏码
          </span>
          <a-dropdown trigger="hover" :popup-max-width="220">
            <div class="header-user-hover">
              <a-avatar :size="32" class="header-avatar">
                {{ displayName.charAt(0) }}
              </a-avatar>
              <div class="header-user-info">
                <span class="header-user">{{ displayName }}</span>
                <span class="header-role">超级管理员</span>
              </div>
            </div>
            <template #content>
              <a-doption @click="openPassword">
                <template #icon><IconSettings /></template>
                修改密码
              </a-doption>
              <a-doption @click="handleLogout">
                <template #icon><IconExport /></template>
                退出登录
              </a-doption>
            </template>
          </a-dropdown>
          <span class="header-divider"></span>
          <a-tooltip content="退出登录">
            <a-button class="logout-btn" type="text" @click="handleLogout">
              <template #icon><IconExport /></template>
            </a-button>
          </a-tooltip>
        </div>
      </a-layout-header>

      <!-- ============ 内容区 ============ -->
      <a-layout-content class="app-content">
        <router-view v-slot="{ Component }">
          <transition name="fade-slide" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </a-layout-content>
    </a-layout>

    <!-- 赞赏码弹窗 -->
    <a-modal
      v-model:visible="rewardVisible"
      :footer="false"
      :width="440"
      :closable="true"
      align-center
      class="reward-modal"
    >
      <div class="reward-body">
        <img :src="REWARD_IMG" alt="赞赏码" class="reward-img" />
        <p class="reward-tip">本系统对你有所帮助的话，请作者喝一杯咖啡！</p>
        <p class="reward-github">
          github项目地址：
          <a :href="GITHUB_URL" target="_blank" rel="noopener">{{ GITHUB_URL }}</a>
        </p>
      </div>
    </a-modal>

    <!-- 修改密码弹窗 -->
    <a-modal
      v-model:visible="pwdVisible"
      title="修改登录密码"
      :width="420"
      :confirm-loading="pwdSaving"
      @ok="submitPassword"
      @cancel="pwdVisible = false"
    >
      <a-form ref="pwdFormRef" :model="pwdForm" :rules="pwdRules" layout="vertical">
        <a-form-item field="oldPassword" label="原密码">
          <a-input-password v-model="pwdForm.oldPassword" placeholder="请输入原密码" allow-clear />
        </a-form-item>
        <a-form-item field="newPassword" label="新密码">
          <a-input-password v-model="pwdForm.newPassword" placeholder="至少 6 位" allow-clear />
        </a-form-item>
        <a-form-item field="confirmPassword" label="确认新密码">
          <a-input-password v-model="pwdForm.confirmPassword" placeholder="请再次输入新密码" allow-clear />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- ============ 右下角任务中心 ============ -->
    <div class="task-center">
      <!-- 展开面板 -->
      <transition name="task-pop">
        <div v-if="taskCenter.panelVisible" class="task-panel">
          <div class="task-panel-header">
            <span class="task-panel-title">
              <IconNotification /> 任务中心
              <span v-if="taskCenter.hasRunning" class="task-running-badge">{{ taskCenter.runningCount }} 个进行中</span>
            </span>
            <a-space :size="4">
              <a-button type="text" size="mini" @click="taskCenter.clearFinished">清除已完成</a-button>
              <a-button type="text" size="mini" @click="taskCenter.togglePanel">
                <template #icon><IconClose /></template>
              </a-button>
            </a-space>
          </div>
          <div class="task-panel-body">
            <div v-if="!taskCenter.tasks.length" class="task-empty">暂无任务</div>
            <div v-for="task in taskCenter.tasks" :key="task.id" class="task-item">
              <div class="task-item-icon" :class="`task-item-icon--${task.status}`">
                <IconLoading v-if="task.status === 'running'" class="spin" />
                <IconCheckCircle v-else-if="task.status === 'success'" />
                <IconCloseCircle v-else />
              </div>
              <div class="task-item-main">
                <div class="task-item-top">
                  <span class="task-item-title">{{ task.title }}</span>
                  <a-tag :color="taskStatusColor(task.status)" size="small">{{ taskStatusText(task.status) }}</a-tag>
                </div>
                <div v-if="task.detail" class="task-item-detail">{{ task.detail }}</div>
                <div class="task-item-msg">
                  {{ task.status === 'running' ? '正在执行中，请稍候…' : task.msg }}
                </div>
                <div class="task-item-time">
                  {{ formatTaskTime(task.startTime) }}
                  <span v-if="task.endTime"> ~ {{ formatTaskTime(task.endTime) }}</span>
                </div>
              </div>
              <a-button
                v-if="task.status !== 'running'"
                type="text"
                size="mini"
                class="task-item-remove"
                @click="taskCenter.remove(task.id)"
              >
                <template #icon><IconClose /></template>
              </a-button>
            </div>
          </div>
        </div>
      </transition>

      <!-- 悬浮按钮 -->
      <div class="task-fab" @click="taskCenter.togglePanel">
        <IconLoading v-if="taskCenter.hasRunning" class="spin" />
        <IconNotification v-else />
        <span v-if="taskCenter.runningCount" class="task-fab-badge">{{ taskCenter.runningCount }}</span>
      </div>
    </div>
  </a-layout>
</template>

<style scoped>
.app-layout {
  min-height: 100vh;
}

/* ============ 侧边栏：深空玻璃质感 ============ */
.app-sider {
  position: relative;
  background:
    radial-gradient(120% 80% at 0% 0%, rgba(28, 55, 100, 0.55) 0%, transparent 55%),
    linear-gradient(165deg, #0e1b32 0%, #0a1528 60%, #081122 100%) !important;
  box-shadow: 1px 0 0 rgba(255, 255, 255, 0.04), 4px 0 24px rgba(0, 0, 0, 0.28);
  z-index: 10;
  overflow: hidden;
}

/* 顶部微光 */
.sider-glow {
  position: absolute;
  top: -120px;
  left: -60px;
  width: 260px;
  height: 260px;
  background: radial-gradient(circle, rgba(64, 128, 255, 0.18) 0%, transparent 70%);
  pointer-events: none;
}

/* ============ Logo ============ */
.logo {
  position: relative;
  height: 72px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 18px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.logo--collapsed {
  padding: 0 15px;
}

.logo-mark {
  position: relative;
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  border-radius: 11px;
  background: linear-gradient(140deg, #4f8cff 0%, #1e5eff 55%, #1447d6 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 19px;
  font-weight: 800;
  font-style: italic;
  letter-spacing: -1px;
  box-shadow: 0 4px 14px rgba(30, 94, 255, 0.45), inset 0 1px 0 rgba(255, 255, 255, 0.3);
}

.logo-text {
  display: flex;
  flex-direction: column;
  line-height: 1.25;
  overflow: hidden;
}

.logo-text strong {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 2.5px;
  color: #f4f7ff;
}

.logo-text small {
  font-size: 10px;
  letter-spacing: 0.5px;
  color: rgba(174, 196, 230, 0.55);
  white-space: nowrap;
}

/* ============ 菜单：彻底消除色块缝隙 ============ */
.app-menu {
  background: transparent !important;
  border-right: 0 !important;
  margin-top: 10px;
  padding: 0 8px;
}

/* 所有菜单项统一透明背景、无外边距缝隙 */
:deep(.arco-menu-dark .arco-menu-item),
:deep(.arco-menu-dark .arco-menu-inline-header) {
  background: transparent !important;
  color: #93a7c4 !important;
  margin: 3px 0 !important;
  border-radius: 9px;
  height: 42px;
  line-height: 42px;
  font-size: 13.5px;
  transition: color 0.2s ease, background 0.2s ease;
}

:deep(.arco-menu-dark .arco-menu-item .arco-icon),
:deep(.arco-menu-dark .arco-menu-inline-header .arco-icon) {
  color: #7f95b5;
  font-size: 16px;
}

/* 悬浮：柔和提亮 */
:deep(.arco-menu-dark .arco-menu-item:hover),
:deep(.arco-menu-dark .arco-menu-inline-header:hover) {
  color: #fff !important;
  background: rgba(255, 255, 255, 0.06) !important;
}

:deep(.arco-menu-dark .arco-menu-item:hover .arco-icon),
:deep(.arco-menu-dark .arco-menu-inline-header:hover .arco-icon) {
  color: #cfe0ff;
}

/* 分组标题（父菜单）：字重更高 */
:deep(.arco-menu-dark .arco-menu-inline-header) {
  font-weight: 600;
  color: #b9c9e2 !important;
}

/* 选中态：左侧指示条 + 柔和渐变，不再用突兀整块蓝色 */
:deep(.arco-menu-dark .arco-menu-item.arco-menu-selected) {
  position: relative;
  color: #fff !important;
  font-weight: 600;
  background: linear-gradient(90deg, rgba(47, 110, 245, 0.38) 0%, rgba(47, 110, 245, 0.06) 100%) !important;
}

:deep(.arco-menu-dark .arco-menu-item.arco-menu-selected::before) {
  content: '';
  position: absolute;
  left: 0;
  top: 9px;
  bottom: 9px;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: linear-gradient(180deg, #6aa1ff, #2f6ef5);
  box-shadow: 0 0 8px rgba(78, 140, 255, 0.8);
}

:deep(.arco-menu-dark .arco-menu-item.arco-menu-selected .arco-icon) {
  color: #8fb6ff;
}

/* 子菜单展开容器：透明，去掉默认深色块 */
:deep(.arco-menu-dark .arco-menu-inline-content) {
  background: transparent !important;
}

:deep(.arco-menu-dark .arco-menu-inline-content .arco-menu-item) {
  padding-left: 42px !important;
}

/* 子菜单项左侧细线，增强层级感 */
:deep(.arco-menu-dark .arco-menu-inline-content)::before {
  content: '';
  position: absolute;
}

/* 展开箭头 */
:deep(.arco-menu-dark .arco-menu-inline-header .arco-menu-icon-suffix) {
  color: #6d84a6;
}

/* ============ 侧边栏底部状态 ============ */
.sider-footer {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 48px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 22px;
  font-size: 12px;
  color: rgba(150, 172, 205, 0.7);
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(0, 0, 0, 0.12);
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #3ddc97;
  box-shadow: 0 0 8px rgba(61, 220, 151, 0.8);
  animation: pulse 2s ease-in-out infinite;
}

.footer-more {
  margin-left: auto;
  font-size: 16px;
  color: rgba(150, 172, 205, 0.5);
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* ============ 主区域 ============ */
.app-main {
  background: #f4f6fb;
  min-width: 0;
}

/* 右上角赞赏码入口 */
.reward-entry {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 13px;
  color: #6b7c93;
  cursor: pointer;
  padding: 6px 10px;
  border-radius: 8px;
  transition: all 0.2s ease;
  white-space: nowrap;
}
.reward-entry:hover {
  color: #d48806;
  background: #fff8e6;
}

/* ============ 顶部栏 ============ */
.app-header {
  height: 72px;
  padding: 0 24px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(12px);
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-shadow: 0 1px 0 rgba(20, 37, 63, 0.05);
  position: sticky;
  top: 0;
  z-index: 9;
}

.header-left,
.header-right {
  display: flex;
  align-items: center;
  gap: 14px;
}

.collapse-btn {
  border: none;
  background: transparent;
  font-size: 20px;
  color: #6b7c93;
  cursor: pointer;
  padding: 8px;
  border-radius: 8px;
  display: inline-flex;
  align-items: center;
  transition: all 0.2s ease;
}

.collapse-btn:hover {
  background: #eef2fa;
  color: #2f6ef5;
}

.header-crumb {
  font-size: 14px;
}

.header-avatar {
  background: linear-gradient(140deg, #4f8cff, #1e5eff);
  color: #fff;
  font-weight: 600;
  box-shadow: 0 2px 8px rgba(30, 94, 255, 0.3);
}

.header-user-hover {
  display: flex;
  align-items: center;
  gap: 14px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 10px;
  transition: background 0.2s ease;
}
.header-user-hover:hover {
  background: #eef2fa;
}

.header-user-info {
  display: flex;
  flex-direction: column;
  line-height: 1.3;
}

.header-user {
  font-size: 13.5px;
  font-weight: 600;
  color: #1d2b42;
}

.header-role {
  font-size: 11px;
  color: #8a99ad;
}

.header-divider {
  width: 1px;
  height: 22px;
  background: #e5eaf2;
  margin: 0 2px;
}

.logout-btn {
  color: #6b7c93;
  font-size: 18px;
}

.logout-btn:hover {
  color: #f53f3f;
  background: #fff1f0;
}

/* ============ 赞赏码弹窗 ============ */
.reward-body {
  text-align: center;
  padding: 4px 0 8px;
}
.reward-img {
  width: 100%;
  max-width: 320px;
  border-radius: 10px;
}
.reward-tip {
  margin: 16px 0 8px;
  font-size: 14px;
  color: #1d2b42;
  font-weight: 600;
}
.reward-github {
  margin: 0;
  font-size: 12px;
  color: #6b7c93;
  word-break: break-all;
}
.reward-github a {
  color: #2f6ef5;
}

/* ============ 内容区 ============ */
.app-content {
  padding: 24px;
  overflow: auto;
}

/* 路由切换动画 */
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.18s ease;
}
.fade-slide-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

/* ============ 右下角任务中心 ============ */
.task-center {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 100;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 12px;
}
.task-fab {
  position: relative;
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: linear-gradient(140deg, #4f8cff, #1e5eff);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  cursor: pointer;
  box-shadow: 0 6px 20px rgba(30, 94, 255, 0.45);
  transition: transform 0.2s ease;
}
.task-fab:hover {
  transform: translateY(-3px);
}
.task-fab-badge {
  position: absolute;
  top: -4px;
  right: -4px;
  min-width: 18px;
  height: 18px;
  padding: 0 4px;
  border-radius: 9px;
  background: #f53f3f;
  color: #fff;
  font-size: 11px;
  line-height: 18px;
  text-align: center;
  border: 2px solid #fff;
}
.task-panel {
  width: 380px;
  max-height: 60vh;
  background: #fff;
  border-radius: 14px;
  box-shadow: 0 12px 40px rgba(20, 37, 63, 0.18);
  border: 1px solid #eef1f6;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.task-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-bottom: 1px solid #f0f2f6;
}
.task-panel-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  font-size: 14px;
  color: #1d2b42;
}
.task-running-badge {
  font-size: 11px;
  font-weight: 500;
  color: #2f6ef5;
  background: #eaf1ff;
  padding: 2px 8px;
  border-radius: 10px;
}
.task-panel-body {
  padding: 8px 12px 12px;
  overflow-y: auto;
}
.task-empty {
  text-align: center;
  color: #8a99ad;
  font-size: 13px;
  padding: 28px 0;
}
.task-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 4px;
  border-bottom: 1px solid #f5f6f9;
}
.task-item:last-child {
  border-bottom: none;
}
.task-item-icon {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  margin-top: 2px;
}
.task-item-icon--running { color: #2f6ef5; }
.task-item-icon--success { color: #00b42a; }
.task-item-icon--error { color: #f53f3f; }
.task-item-main {
  flex: 1;
  min-width: 0;
}
.task-item-top {
  display: flex;
  align-items: center;
  gap: 8px;
}
.task-item-title {
  font-size: 13px;
  font-weight: 600;
  color: #1d2b42;
}
.task-item-detail {
  font-size: 12px;
  color: #6b7c93;
  margin-top: 2px;
}
.task-item-msg {
  font-size: 12px;
  color: #4e5969;
  margin-top: 4px;
  word-break: break-all;
}
.task-item-time {
  font-size: 11px;
  color: #a5b0c0;
  margin-top: 4px;
}
.task-item-remove {
  flex-shrink: 0;
}
.spin {
  animation: task-spin 1s linear infinite;
}
@keyframes task-spin {
  to { transform: rotate(360deg); }
}
.task-pop-enter-active,
.task-pop-leave-active {
  transition: all 0.18s ease;
  transform-origin: bottom right;
}
.task-pop-enter-from,
.task-pop-leave-to {
  opacity: 0;
  transform: scale(0.92) translateY(8px);
}
</style>
