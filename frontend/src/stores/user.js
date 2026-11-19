import { defineStore } from 'pinia'
import { ref } from 'vue'
import { authApi } from '@/api/modules'
import { TOKEN_KEY } from '@/api/request'

const USER_KEY = 'zlzchat_user'

/** 用户状态：令牌、用户信息及登录/登出动作 */
export const useUserStore = defineStore('user', () => {
  // ---------- 响应式状态 ----------
  const token = ref(localStorage.getItem(TOKEN_KEY) || '')
  const userInfo = ref(JSON.parse(localStorage.getItem(USER_KEY) || 'null') || null)

  // ---------- 动作 ----------
  async function login(payload) {
    const data = await authApi.login(payload)
    token.value = data.token
    userInfo.value = data.userInfo
    localStorage.setItem(TOKEN_KEY, data.token)
    localStorage.setItem(USER_KEY, JSON.stringify(data.userInfo || {}))
    return data
  }

  async function logout() {
    try {
      await authApi.logout()
    } catch (e) {
      // 登出接口失败也要清理本地状态
    }
    token.value = ''
    userInfo.value = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  }

  async function fetchInfo() {
    const data = await authApi.info()
    userInfo.value = data
    localStorage.setItem(USER_KEY, JSON.stringify(data || {}))
    return data
  }

  return { token, userInfo, login, logout, fetchInfo }
})
