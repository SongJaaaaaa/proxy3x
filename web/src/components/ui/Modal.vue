<script setup lang="ts">
import { watch } from 'vue'
import Icon from './Icon.vue'

/**
 * Modal —— 玻璃弹框外壳（对应 stitch 新增用户/新增家宽弹框）。
 * 霓虹描边 + 暗色遮罩；打开时锁定背景滚动。
 * slots: title / default(表单内容) / footer。
 */
const props = defineProps<{ open: boolean; title: string; icon?: string; iconTone?: 'green' | 'purple' }>()
const emit = defineEmits<{ close: [] }>()

watch(
  () => props.open,
  (v) => {
    document.body.style.overflow = v ? 'hidden' : ''
  },
)
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="open"
        class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
        @click.self="emit('close')"
      >
        <div
          class="w-full max-w-xl rounded-xl glass-panel shadow-[0_8px_40px_rgba(0,0,0,0.5)] flex flex-col max-h-[90vh]"
          :style="{
            boxShadow:
              iconTone === 'purple'
                ? '0 8px 40px rgba(163,43,255,0.18)'
                : '0 8px 40px rgba(36,255,205,0.15)',
          }"
        >
          <!-- 标题栏 -->
          <div class="flex items-center justify-between px-6 py-4 border-b border-outline-variant/15">
            <div class="flex items-center gap-2 font-title-sm text-title-sm text-on-surface">
              <Icon
                v-if="icon"
                :name="icon"
                :size="22"
                :class="iconTone === 'purple' ? 'text-primary' : 'text-secondary-fixed'"
              />
              <span>{{ title }}</span>
            </div>
            <button class="text-outline hover:text-on-surface transition-colors" @click="emit('close')">
              <Icon name="close" :size="22" />
            </button>
          </div>
          <!-- 内容 -->
          <div class="px-6 py-5 overflow-y-auto flex flex-col gap-4">
            <slot />
          </div>
          <!-- 底部操作 -->
          <div class="px-6 py-4 border-t border-outline-variant/15 flex justify-end gap-3">
            <slot name="footer" />
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
