import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api/endpoints'
import type { LoginPayload } from '@/types/auth'

/**
 * 鉴权状态。会话靠 HttpOnly cookie，store 只缓存登录态与用户名。
 */
export const useAuthStore = defineStore('auth', () => {
  const username = ref<string | null>(null)
  const isAuthenticated = ref(false)
  const checked = ref(false)

  async function fetchMe() {
    try {
      const res = await api.me()
      isAuthenticated.value = !!res.ok
      username.value = res.username ?? null
    } catch {
      isAuthenticated.value = false
      username.value = null
    } finally {
      checked.value = true
    }
  }

  async function login(payload: LoginPayload) {
    await api.login(payload)
    isAuthenticated.value = true
    username.value = payload.username
  }

  async function logout() {
    try {
      await api.logout()
    } finally {
      isAuthenticated.value = false
      username.value = null
    }
  }

  return { username, isAuthenticated, checked, fetchMe, login, logout }
})
