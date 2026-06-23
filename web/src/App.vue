<script setup lang="ts">
import { RouterView } from 'vue-router'
import { Toaster } from 'vue-sonner'

/**
 * 根组件：路由出口 + 全局 toast（操作成功/失败提示统一从这里弹）。
 */
</script>

<template>
  <RouterView />
  <Toaster theme="dark" position="top-right" rich-colors />
</template>
