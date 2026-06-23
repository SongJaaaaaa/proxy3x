<script setup lang="ts">
import { computed } from 'vue'
import { cn } from '@/lib/utils'

/**
 * Badge —— 状态/协议徽章。tone 决定配色，dot 显示前置圆点。
 * tone: blue(协议/HTTP) / purple(SOCKS5) / green(可用) / red(不可用) / gray(未检测)
 */
const props = withDefaults(
  defineProps<{ tone?: 'blue' | 'purple' | 'green' | 'red' | 'gray'; dot?: boolean; pulse?: boolean }>(),
  { tone: 'gray', dot: false, pulse: false },
)

const wrap = computed(() =>
  cn(
    'px-2 py-0.5 rounded-full font-label-sm text-[10px] tracking-wider inline-flex items-center gap-1 border',
    props.tone === 'blue' && 'border-primary/30 bg-primary/10 text-primary uppercase',
    props.tone === 'purple' && 'border-tertiary-container/30 bg-tertiary-container/10 text-tertiary-container uppercase',
    props.tone === 'green' && 'border-secondary-fixed/30 bg-secondary-fixed/10 text-secondary-fixed',
    props.tone === 'red' && 'border-error/30 bg-error/10 text-error',
    props.tone === 'gray' && 'border-outline-variant/50 bg-outline-variant/10 text-outline',
  ),
)
const dotCls = computed(() =>
  cn(
    'w-1.5 h-1.5 rounded-full',
    props.tone === 'green' && 'bg-secondary-fixed',
    props.tone === 'red' && 'bg-error',
    props.tone === 'gray' && 'bg-outline',
    props.tone === 'blue' && 'bg-primary',
    props.tone === 'purple' && 'bg-tertiary-container',
    props.pulse && 'animate-pulse',
  ),
)
</script>

<template>
  <span :class="wrap">
    <span v-if="dot" :class="dotCls"></span>
    <slot />
  </span>
</template>
