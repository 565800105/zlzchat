import axios from 'axios'
import { Message } from '@arco-design/web-vue'

/**
 * 统一请求封装
 * - baseURL 指向 /api（由 Vite 代理到后端 8100）
 * - 请求拦截器自动携带 Authorization: Bearer <token>
 * - 响应拦截器统一处理业务码：code !== 200 弹 Message 并中断
 */
const request = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

// token 存储的 key（与 user store 保持一致）
export const TOKEN_KEY = 'zlzchat_token'

request.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem(TOKEN_KEY)
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error),
)

request.interceptors.response.use(
  (response) => {
    const res = response.data

    // 后端统一响应：{ code, msg, data }
    if (res && typeof res === 'object' && 'code' in res) {
      if (res.code === 200) {
        return res
      }

      // 登录态失效：清理本地令牌并跳转登录
      if (res.code === 401) {
        localStorage.removeItem(TOKEN_KEY)
        Message.warning(res.msg || '登录已过期，请重新登录')
        import('@/router').then(({ default: router }) => {
          if (router.currentRoute.value.name !== 'login') {
            router.push('/login')
          }
        })
        return Promise.reject(new Error(res.msg || '登录已过期'))
      }

      // 其余业务错误统一提示
      Message.error(res.msg || '操作失败')
      return Promise.reject(new Error(res.msg || '操作失败'))
    }

    // 非统一结构（如文件下载）直接放行
    return res
  },
  (error) => {
    const status = error.response?.status
    if (status === 401) {
      localStorage.removeItem(TOKEN_KEY)
      Message.warning('登录已过期，请重新登录')
      import('@/router').then(({ default: router }) => router.push('/login'))
    } else {
      Message.error(error.response?.data?.msg || error.message || '网络异常')
    }
    return Promise.reject(error)
  },
)

export default request
