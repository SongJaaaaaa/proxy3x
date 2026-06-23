<script setup lang="ts">
import { computed } from 'vue'
import { cn } from '@/lib/utils'

/**
 * Button —— 统一按钮。variant: primary(渐变) / ghost(描边) / danger / subtle。
 * 高度固定 40px（桌面），与 stitch 设计一致。
 */
const props = withDefaults(
  defineProps<{
    variant?: 'primary' | 'ghost' | 'danger' | 'subtle'
    type?: 'button' | 'submit'
    disabled?: boolean
    loading?: boolean
    block?: boolean
  }>(),
  { variant: 'ghost', type: 'button', disabled: false, loading: false, block: false },
)

const classes = computed(() =>
  cn(
    'h-10 px-5 rounded-lg font-label-sm text-label-sm font-semibold inline-flex items-center justify-center gap-2 transition-all active:scale-95 disabled:opacity-50 disabled:pointer-events-none',
    props.block && 'w-full',
    props.variant === 'primary' &&
      'btn-gradient hover:opacity-90 hover:shadow-[0_4px_16px_rgba(0,102,255,0.3)]',
    props.variant === 'ghost' &&
      'border border-outline-variant/50 text-on-surface-variant hover:text-primary hover:border-primary/50 bg-surface-container-lowest/30',
    props.variant === 'danger' &&
      'border border-error/50 text-error hover:bg-error/10 bg-surface-container-lowest/30',
    props.variant === 'subtle' && 'text-on-surface-variant hover:text-on-surface hover:bg-surface-variant/30',
  ),
)
</script>

<template>
  <button :type="type" :class="classes" :disabled="disabled || loading">
    <span v-if="loading" class="material-symbols-outlined text-[18px] animate-spin">progress_activity</span>
    <slot />
  </button>
</template>
