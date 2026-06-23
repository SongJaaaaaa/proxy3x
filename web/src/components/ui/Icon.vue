<script setup lang="ts">
/**
 * Icon —— Material Symbols Outlined 图标。与 stitch 参考 UI 同一套图标。
 * props: name=图标名, size=字号(px), fill=是否实心。
 */
withDefaults(defineProps<{ name: string; size?: number; fill?: boolean }>(), {
  size: 20,
  fill: false,
})
</script>

<template>
  <span
    class="material-symbols-outlined select-none"
    :style="{
      fontSize: size + 'px',
      fontVariationSettings: fill ? `'FILL' 1` : `'FILL' 0`,
    }"
    >{{ name }}</span
  >
</template>
