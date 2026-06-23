<script setup lang="ts">
import { computed } from 'vue'
import Icon from './Icon.vue'

/**
 * Pagination —— 通用分页条（暗色玻璃风）。
 * v-model:page 当前页(1起)，v-model:pageSize 每页条数(可调)。
 * total 总条数；pageSizeOptions 每页条数候选。
 */
const props = withDefaults(
  defineProps<{ total: number; pageSizeOptions?: number[] }>(),
  { pageSizeOptions: () => [10, 20, 50] },
)
const page = defineModel<number>('page', { required: true })
const pageSize = defineModel<number>('pageSize', { required: true })

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / pageSize.value)))

const rangeText = computed(() => {
  if (props.total === 0) return '0'
  const start = (page.value - 1) * pageSize.value + 1
  const end = Math.min(page.value * pageSize.value, props.total)
  return `${start}–${end}`
})

// 页码列表（超过 7 页时用省略号收拢）
const pages = computed<(number | '…')[]>(() => {
  const tp = totalPages.value
  const cur = page.value
  if (tp <= 7) return Array.from({ length: tp }, (_, i) => i + 1)
  const out: (number | '…')[] = [1]
  const left = Math.max(2, cur - 1)
  const right = Math.min(tp - 1, cur + 1)
  if (left > 2) out.push('…')
  for (let i = left; i <= right; i++) out.push(i)
  if (right < tp - 1) out.push('…')
  out.push(tp)
  return out
})

function go(p: number) {
  if (p < 1 || p > totalPages.value) return
  page.value = p
}
function onSizeChange(e: Event) {
  pageSize.value = Number((e.target as HTMLSelectElement).value)
  page.value = 1
}
</script>

<template>
  <div class="flex items-center justify-between gap-3 flex-wrap shrink-0 py-1">
    <!-- 左：统计 + 每页条数 -->
    <div class="flex items-center gap-3 font-label-sm text-label-sm text-on-surface-variant">
      <span>共 {{ total }} 条 · 显示 {{ rangeText }}</span>
      <div class="flex items-center gap-1.5">
        <span class="text-outline">每页</span>
        <select
          class="control !h-8 !w-auto !px-2 !pr-7 text-sm"
          :value="pageSize"
          @change="onSizeChange"
        >
          <option v-for="opt in pageSizeOptions" :key="opt" :value="opt">{{ opt }}</option>
        </select>
        <span class="text-outline">条</span>
      </div>
    </div>

    <!-- 右：页码导航 -->
    <div class="flex items-center gap-1">
      <button
        type="button"
        class="w-8 h-8 rounded-lg border border-outline-variant/40 text-on-surface-variant hover:text-on-surface hover:border-primary/50 disabled:opacity-40 disabled:pointer-events-none flex items-center justify-center transition-colors"
        :disabled="page <= 1"
        @click="go(page - 1)"
      >
        <Icon name="chevron_left" :size="18" />
      </button>

      <template v-for="(p, i) in pages" :key="i">
        <span v-if="p === '…'" class="w-8 h-8 flex items-center justify-center text-outline text-sm">…</span>
        <button
          v-else
          type="button"
          class="min-w-8 h-8 px-2 rounded-lg text-sm font-label-sm transition-colors"
          :class="
            p === page
              ? 'bg-primary text-on-primary font-semibold'
              : 'border border-outline-variant/40 text-on-surface-variant hover:text-on-surface hover:border-primary/50'
          "
          @click="go(p as number)"
        >
          {{ p }}
        </button>
      </template>

      <button
        type="button"
        class="w-8 h-8 rounded-lg border border-outline-variant/40 text-on-surface-variant hover:text-on-surface hover:border-primary/50 disabled:opacity-40 disabled:pointer-events-none flex items-center justify-center transition-colors"
        :disabled="page >= totalPages"
        @click="go(page + 1)"
      >
        <Icon name="chevron_right" :size="18" />
      </button>
    </div>
  </div>
</template>
