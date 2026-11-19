<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { IconUser, IconLock, IconEye, IconEyeInvisible } from '@arco-design/web-vue/es/icon'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

// ---------- 响应式状态 ----------
const formRef = ref()
const loading = ref(false)
const visible = ref(false)

// 修改过密码后不再预填默认密码（layout 在改密成功后写入标记）
const passwordChanged = localStorage.getItem('zlzchat_password_changed') === '1'
const form = reactive({
  username: 'admin',
  password: passwordChanged ? '' : 'admin123',
})

const rules = {
  username: [{ required: true, message: '请输入用户名' }],
  password: [{ required: true, message: '请输入密码' }],
}

// ---------- 事件处理 ----------
async function handleSubmit() {
  try {
    await formRef.value?.validate()
  } catch (e) {
    return
  }
  loading.value = true
  try {
    await userStore.login({ username: form.username, password: form.password })
    Message.success('登录成功')
    // 标记本次为「登录后进入」，layout 据此弹出赞赏码（每次登录弹一次，刷新不重复）
    sessionStorage.setItem('zlzchat_reward_on_login', '1')
    router.push('/')
  } catch (e) {
    // 错误信息已由 request 拦截器统一提示
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-bg">
      <div class="bg-circle circle-1"></div>
      <div class="bg-circle circle-2"></div>
      <div class="bg-circle circle-3"></div>
    </div>

    <div class="login-card">
      <div class="login-brand">
        <div class="brand-mark">CN</div>
        <h1>ZLZCHAT 公众号信息管理系统</h1>
        <p>内容采集 · 智能分类 · 定时同步</p>
      </div>

      <a-form ref="formRef" :model="form" :rules="rules" layout="vertical" @submit="handleSubmit">
        <a-form-item field="username" label="用户名">
          <a-input v-model="form.username" placeholder="请输入用户名" size="large" allow-clear>
            <template #prefix><IconUser /></template>
          </a-input>
        </a-form-item>

        <a-form-item field="password" label="密码">
          <a-input
            v-model="form.password"
            :type="visible ? 'text' : 'password'"
            placeholder="请输入密码"
            size="large"
            allow-clear
          >
            <template #prefix><IconLock /></template>
            <template #suffix>
              <button class="eye-btn" type="button" @click="visible = !visible">
                <IconEyeInvisible v-if="visible" />
                <IconEye v-else />
              </button>
            </template>
          </a-input>
        </a-form-item>

        <a-form-item>
          <a-button type="primary" html-type="submit" size="large" long :loading="loading">
            登 录
          </a-button>
        </a-form-item>
      </a-form>

      <div class="login-tip">默认账号 admin / admin123</div>
    </div>

    <div class="login-footer">© ZLZCHAT · 公众号信息管理平台</div>
  </div>
</template>

<style scoped>
.login-page {
  position: relative;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1d3a6e 0%, #12294f 50%, #0d1f3d 100%);
  overflow: hidden;
}

.login-bg {
  position: absolute;
  inset: 0;
}

.bg-circle {
  position: absolute;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(64, 128, 255, 0.35), rgba(22, 93, 255, 0.05));
}
.circle-1 {
  width: 520px;
  height: 520px;
  top: -180px;
  left: -120px;
}
.circle-2 {
  width: 420px;
  height: 420px;
  bottom: -160px;
  right: -100px;
  background: linear-gradient(135deg, rgba(0, 180, 42, 0.18), rgba(64, 128, 255, 0.05));
}
.circle-3 {
  width: 260px;
  height: 260px;
  top: 40%;
  right: 18%;
  background: linear-gradient(135deg, rgba(255, 125, 0, 0.14), transparent);
}

.login-card {
  position: relative;
  z-index: 2;
  width: 420px;
  max-width: calc(100vw - 40px);
  background: rgba(255, 255, 255, 0.98);
  border-radius: 18px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  padding: 40px 40px 32px;
}

.login-brand {
  text-align: center;
  margin-bottom: 28px;
}

.brand-mark {
  width: 58px;
  height: 58px;
  margin: 0 auto 16px;
  border-radius: 16px;
  background: linear-gradient(135deg, #4080ff, #165dff);
  color: #fff;
  font-size: 20px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 20px rgba(22, 93, 255, 0.4);
}

.login-brand h1 {
  font-size: 20px;
  margin: 0 0 6px;
  color: #1d2129;
}

.login-brand p {
  margin: 0;
  font-size: 13px;
  color: #86909c;
  letter-spacing: 2px;
}

.eye-btn {
  border: none;
  background: transparent;
  cursor: pointer;
  color: #86909c;
  font-size: 16px;
  display: inline-flex;
  padding: 4px;
}

.login-tip {
  text-align: center;
  margin-top: 16px;
  font-size: 12px;
  color: #a9aeb8;
}

.login-footer {
  position: absolute;
  bottom: 24px;
  z-index: 2;
  color: rgba(255, 255, 255, 0.55);
  font-size: 12px;
}
</style>
