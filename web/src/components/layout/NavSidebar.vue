<script setup lang="ts">
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import Icon from '@/components/ui/Icon.vue'

/**
 * NavSidebar —— 固定左侧导航（240px）。品牌区 + 总览/用户套餐/家宽池 + 底部退出。
 * 与 stitch 参考 UI 一致：玻璃背景、激活项左侧绿色描边。
 */
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const items = [
  { to: '/dashboard', label: '总览', icon: 'dashboard' },
  { to: '/packages', label: '用户套餐', icon: 'inventory_2' },
  { to: '/upstreams', label: '家宽池', icon: 'lan' },
]

async function logout() {
  await auth.logout()
  router.push('/login')
}
</script>

<template>
  <nav
    class="w-[240px] h-screen fixed left-0 top-0 z-40 flex flex-col p-gutter bg-background/80 backdrop-blur-xl border-r border-outline-variant/20 shadow-[0_8px_32px_rgba(0,0,0,0.4)]"
  >
    <!-- 品牌 -->
    <div class="mb-8 px-2 flex items-center gap-3">
      <div
        class="w-10 h-10 rounded-lg bg-surface-variant flex items-center justify-center border border-outline-variant/30 shrink-0"
      >
        <Icon name="dns" :size="22" fill class="text-primary" />
      </div>
      <div>
        <h1 class="text-xl font-bold bg-gradient-to-br from-primary to-secondary-fixed bg-clip-text text-transparent leading-none">
          proxy3x
        </h1>
        <p class="font-label-sm text-label-sm text-on-surface-variant mt-1">链式代理管理</p>
      </div>
    </div>

    <!-- 主导航 -->
    <div class="flex flex-col gap-2 flex-1">
      <RouterLink
        v-for="it in items"
        :key="it.to"
        :to="it.to"
        class="flex items-center gap-3 px-4 py-3 rounded-lg transition-colors active:scale-95"
        :class="
          route.path === it.to
            ? 'bg-primary-container/20 text-secondary-fixed-dim border-l-4 border-secondary-fixed font-semibold'
            : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-variant/30'
        "
      >
        <Icon :name="it.icon" :fill="route.path === it.to" />
        <span class="font-body-md text-body-md">{{ it.label }}</span>
      </RouterLink>
    </div>

    <!-- 底部 -->
    <div class="mt-auto flex flex-col gap-2">
      <div class="h-px w-full bg-outline-variant/20 my-2"></div>
      <div class="px-2 flex items-center gap-2 text-on-surface-variant">
        <Icon name="account_circle" :size="20" />
        <span class="font-body-md text-sm truncate">{{ auth.username || 'admin' }}</span>
      </div>
      <button
        class="flex items-center gap-3 px-4 py-2 rounded-lg text-on-surface-variant hover:text-error hover:bg-error/10 transition-colors"
        @click="logout"
      >
        <Icon name="logout" :size="20" />
        <span class="font-body-md text-sm">退出登录</span>
      </button>
    </div>
  </nav>
</template>
