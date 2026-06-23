<script setup lang="ts">
/**
 * Field —— 表单字段外壳：label（可标必填）+ 插槽放 input/select/textarea。
 * 统一标签样式与间距，对应 stitch 弹框表单。
 */
withDefaults(defineProps<{ label: string; required?: boolean; hint?: string }>(), {
  required: false,
})
</script>

<template>
  <label class="flex flex-col gap-2">
    <span class="flex items-center justify-between">
      <span class="font-label-sm text-label-sm text-on-surface-variant">
        {{ label }}
        <span v-if="required" class="text-secondary-fixed">*</span>
      </span>
      <span v-if="hint" class="font-code-xs text-[11px] text-outline bg-surface-container-lowest/60 px-2 py-0.5 rounded">
        {{ hint }}
      </span>
    </span>
    <slot />
  </label>
</template>
