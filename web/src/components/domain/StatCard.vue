<script setup lang="ts">
import Icon from '@/components/ui/Icon.vue'

/**
 * StatCard —— 总览汇总卡片（对应 stitch proxy3x_3 顶部 4 张卡）。
 * tone 控制图标/强调色：blue/green/purple/red。
 */
withDefaults(
  defineProps<{
    icon: string
    label: string
    value: string
    unit?: string
    tone?: 'blue' | 'green' | 'purple' | 'red'
  }>(),
  { tone: 'blue' },
)

const toneClass: Record<string, string> = {
  blue: 'text-primary',
  green: 'text-secondary-fixed',
  purple: 'text-tertiary-container',
  red: 'text-error',
}
</script>

<template>
  <div class="glass-panel rounded-xl p-5 flex flex-col gap-3 neon-border-hover transition-all">
    <div class="flex items-center justify-between">
      <span class="font-label-sm text-label-sm text-on-surface-variant">{{ label }}</span>
      <div class="w-8 h-8 rounded-lg bg-surface-variant/40 flex items-center justify-center">
        <Icon :name="icon" :size="18" :class="toneClass[tone]" />
      </div>
    </div>
    <div class="flex items-end gap-1">
      <span class="text-3xl font-bold text-on-surface leading-none">{{ value }}</span>
      <span v-if="unit" class="font-body-md text-sm text-on-surface-variant mb-0.5">{{ unit }}</span>
    </div>
  </div>
</template>
