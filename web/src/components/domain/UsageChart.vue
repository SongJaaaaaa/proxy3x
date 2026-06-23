<script setup lang="ts">
import { computed } from 'vue'
import type { Package } from '@/types/dashboard'

/**
 * UsageChart —— 套餐用量分布柱状图（对应 stitch proxy3x_3，纯 CSS 柱，无历史时序）。
 * 每个套餐一根柱，高度 = 总用量/总额度占比；颜色蓝→紫渐变。
 */
const props = defineProps<{ packages: Package[] }>()

const bars = computed(() =>
  props.packages.slice(0, 12).map((p) => {
    const pct = p.total_gb > 0 ? Math.min(100, (p.total_used_gb / p.total_gb) * 100) : 0
    return { name: p.name, pct: Math.round(pct), used: p.total_used_gb, total: p.total_gb }
  }),
)
</script>

<template>
  <div class="glass-panel rounded-xl p-5 flex flex-col gap-4">
    <div class="flex items-center justify-between">
      <h3 class="font-title-sm text-title-sm text-on-surface">套餐用量分布</h3>
      <span class="font-label-sm text-label-sm text-on-surface-variant">总用量占总额度比例</span>
    </div>

    <div v-if="bars.length" class="flex items-end gap-3 h-48 pt-2">
      <div v-for="b in bars" :key="b.name" class="flex-1 flex flex-col items-center gap-2 group min-w-0">
        <span class="font-code-xs text-[10px] text-on-surface-variant opacity-0 group-hover:opacity-100 transition-opacity">
          {{ b.used.toFixed(1) }}/{{ b.total }}G
        </span>
        <div class="w-full flex-1 flex items-end">
          <div
            class="w-full rounded-t bg-gradient-to-t from-primary-container to-tertiary-container transition-all duration-700"
            :style="{ height: Math.max(2, b.pct) + '%' }"
          ></div>
        </div>
        <span class="font-label-sm text-[10px] text-outline truncate w-full text-center">{{ b.name }}</span>
      </div>
    </div>
    <div v-else class="h-48 flex items-center justify-center text-outline font-body-md text-sm">暂无套餐数据</div>
  </div>
</template>
