<script setup lang="ts">
import { computed } from 'vue'

/**
 * ProgressBar —— 用量进度条。蓝→紫渐变（对应 stitch 进度条规范）。
 * percent 为 null 时显示「未设额度」灰条（家宽 quota_gb=0 场景）。
 * muted=true 走灰色（不可用/未检测节点）。
 */
const props = withDefaults(
  defineProps<{ percent: number | null; muted?: boolean }>(),
  { muted: false },
)

const width = computed(() => {
  if (props.percent === null) return '0%'
  return Math.min(100, Math.max(0, props.percent)) + '%'
})
const over = computed(() => props.percent !== null && props.percent >= 100)
</script>

<template>
  <div class="w-full h-1.5 bg-surface-container-high rounded-full overflow-hidden">
    <div
      v-if="percent !== null"
      class="h-full rounded-full transition-all duration-500"
      :class="
        muted
          ? 'bg-outline-variant'
          : over
            ? 'bg-error'
            : 'bg-gradient-to-r from-primary-container to-tertiary-container shadow-[0_0_10px_rgba(163,43,255,0.5)]'
      "
      :style="{ width }"
    ></div>
  </div>
</template>
