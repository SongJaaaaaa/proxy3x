<script setup lang="ts">
import NavSidebar from './NavSidebar.vue'

/**
 * AppShell —— 已登录页面的统一框架：左侧 NavSidebar + 顶部操作条 + 内容区。
 * 顶部条左侧放页面标题（title 插槽），右侧放页面级操作（actions 插槽）。
 */
defineProps<{ title: string; subtitle?: string }>()
</script>

<template>
  <div class="bg-glow h-screen overflow-hidden">
    <NavSidebar />

    <!-- 顶部操作条 -->
    <header
      class="h-16 fixed top-0 right-0 w-[calc(100%-240px)] z-30 flex justify-between items-center px-container-padding bg-surface/50 backdrop-blur-md border-b border-outline-variant/10"
    >
      <div>
        <h2 class="font-headline-md text-headline-md text-on-surface tracking-tight leading-none">{{ title }}</h2>
        <p v-if="subtitle" class="font-body-md text-body-md text-on-surface-variant mt-1">{{ subtitle }}</p>
      </div>
      <div class="flex items-center gap-3">
        <slot name="actions" />
      </div>
    </header>

    <!-- 内容区：仅此处滚动，整页不滚动 -->
    <main
      class="ml-[240px] mt-16 h-[calc(100vh-64px)] overflow-y-auto p-container-padding flex flex-col gap-panel-gap"
    >
      <slot />
    </main>
  </div>
</template>
