<script setup lang="ts">
import { RouterView } from 'vue-router'
import { Toaster } from 'vue-sonner'
import { useTheme } from '@/composables/useTheme'

/**
 * 根组件：路由出口 + 全局 toast（操作成功/失败提示统一从这里弹）。
 * Toaster 主题跟随全局明暗主题。
 */
const { theme } = useTheme()
</script>

<template>
  <RouterView />
  <Toaster :theme="theme" position="top-right" rich-colors />
</template>
