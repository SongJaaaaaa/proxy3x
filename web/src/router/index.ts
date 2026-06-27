import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { setUnauthorizedHandler } from '@/api/client'

/**
 * 路由表 + 登录守卫。
 * - /login 公开；其余需登录，未登录跳 /login。
 * - 注册 client 的 401 钩子：会话过期时任何请求都会把用户弹回登录页。
 */
const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/dashboard' },
    { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue'), meta: { public: true } },
    { path: '/dashboard', name: 'dashboard', component: () => import('@/views/DashboardView.vue') },
    { path: '/packages', name: 'packages', component: () => import('@/views/PackagesView.vue') },
    { path: '/upstreams', name: 'upstreams', component: () => import('@/views/UpstreamsView.vue') },
    { path: '/socks-sources', name: 'socks-sources', component: () => import('@/views/SocksSourcesView.vue') },
    { path: '/socks-sources/:id', name: 'socks-source-detail', component: () => import('@/views/SocksSourceDetailView.vue') },
    { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
  ],
})

setUnauthorizedHandler(() => {
  if (router.currentRoute.value.name !== 'login') {
    router.push('/login')
  }
})

router.beforeEach(async (to) => {
  if (to.meta.public) return true
  const auth = useAuthStore()
  if (!auth.checked) await auth.fetchMe()
  if (!auth.isAuthenticated) return { name: 'login' }
  return true
})

export default router
