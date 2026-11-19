import { createRouter, createWebHistory } from 'vue-router'
import { TOKEN_KEY } from '@/api/request'

/** 后台路由：除 /login 外全部需要登录 */
const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/login/index.vue'),
    meta: { title: '登录', public: true },
  },
  {
    path: '/',
    component: () => import('@/layout/index.vue'),
    redirect: '/admin/cms/classification',
    children: [
      {
        path: 'admin/cms/classification',
        name: 'classification',
        component: () => import('@/views/cms/classification/index.vue'),
        meta: { title: '订阅源分类' },
      },
      {
        path: 'admin/cms/updateLog',
        name: 'updateLog',
        component: () => import('@/views/cms/updateLog/index.vue'),
        meta: { title: '更新记录' },
      },
      {
        path: 'admin/cms/feeds',
        name: 'feeds',
        component: () => import('@/views/cms/feeds/index.vue'),
        meta: { title: '公众号信息' },
      },
      {
        path: 'admin/cms/mparticles',
        name: 'mparticles',
        component: () => import('@/views/cms/mparticles/index.vue'),
        meta: { title: '文章信息' },
      },
      {
        path: 'admin/cms/accounts',
        name: 'accounts',
        component: () => import('@/views/cms/accounts/index.vue'),
        meta: { title: '账号配置' },
      },
      {
        path: 'admin/cms/config',
        name: 'config',
        component: () => import('@/views/cms/config/index.vue'),
        meta: { title: '配置项管理' },
      },
      {
        path: 'admin/monitor/job',
        name: 'job',
        component: () => import('@/views/monitor/job/index.vue'),
        meta: { title: '定时任务配置' },
      },
      {
        path: 'admin/monitor/logs',
        name: 'logs',
        component: () => import('@/views/logs/index.vue'),
        meta: { title: '请求日志' },
      },
      {
        path: 'admin/monitor/runLogs',
        name: 'runLogs',
        component: () => import('@/views/runLogs/index.vue'),
        meta: { title: '运行日志' },
      },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

// 登录守卫：无 token 重定向到 /login；已登录访问 /login 则回到首页
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (to.meta.public) {
    if (token && to.name === 'login') {
      next('/')
    } else {
      next()
    }
    return
  }
  if (!token) {
    next('/login')
  } else {
    next()
  }
})

export default router
