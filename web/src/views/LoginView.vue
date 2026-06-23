<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ApiError } from '@/api/errors'
import Icon from '@/components/ui/Icon.vue'

/**
 * 登录页（对应 stitch proxy3x_1）。居中玻璃卡，用户名/密码 + 渐变登录按钮，
 * 失败原因内联显示在按钮下方。
 */
const router = useRouter()
const auth = useAuthStore()

const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await auth.login({ username: username.value, password: password.value })
    router.push('/dashboard')
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="bg-glow min-h-screen flex items-center justify-center p-4">
    <form
      class="w-full max-w-md glass-panel rounded-xl p-8 flex flex-col"
      @submit.prevent="submit"
    >
      <!-- 品牌 -->
      <div class="text-center mb-8">
        <h1 class="text-display-lg font-bold bg-gradient-to-br from-primary to-secondary-fixed bg-clip-text text-transparent">
          proxy3x
        </h1>
        <p class="font-body-md text-body-md text-on-surface-variant mt-1">链式代理管理</p>
      </div>

      <!-- 用户名 -->
      <label class="font-label-sm text-label-sm text-on-surface-variant mb-2">用户名</label>
      <div class="relative mb-5">
        <Icon name="person" :size="20" class="absolute left-3 top-1/2 -translate-y-1/2 text-outline" />
        <input v-model="username" class="control pl-10" placeholder="输入管理员账号" autocomplete="username" />
      </div>

      <!-- 密码 -->
      <label class="font-label-sm text-label-sm text-on-surface-variant mb-2">密码</label>
      <div class="relative mb-6">
        <Icon name="lock" :size="20" class="absolute left-3 top-1/2 -translate-y-1/2 text-outline" />
        <input
          v-model="password"
          type="password"
          class="control pl-10"
          placeholder="输入密码"
          autocomplete="current-password"
        />
      </div>

      <!-- 登录按钮 -->
      <button
        type="submit"
        class="btn-gradient h-12 rounded-lg flex items-center justify-center gap-2 hover:opacity-90 transition-opacity active:scale-[0.98] disabled:opacity-60"
        :disabled="loading"
      >
        <span v-if="loading" class="material-symbols-outlined animate-spin text-[20px]">progress_activity</span>
        <template v-else>登录 <Icon name="arrow_forward" :size="18" /></template>
      </button>

      <!-- 错误 -->
      <p v-if="error" class="mt-4 text-center font-body-md text-sm text-error">{{ error }}</p>
    </form>
  </div>
</template>
