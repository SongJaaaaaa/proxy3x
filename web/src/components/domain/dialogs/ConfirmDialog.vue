<script setup lang="ts">
import Modal from '@/components/ui/Modal.vue'
import Button from '@/components/ui/Button.vue'

/**
 * ConfirmDialog —— 通用确认弹框（删除家宽/套餐前确认）。
 */
defineProps<{ open: boolean; title: string; message: string; busy?: boolean }>()
const emit = defineEmits<{ close: []; confirm: [] }>()
</script>

<template>
  <Modal :open="open" :title="title" icon="warning" icon-tone="purple" @close="emit('close')">
    <p class="font-body-md text-body-md text-on-surface-variant leading-relaxed">{{ message }}</p>
    <template #footer>
      <Button variant="ghost" @click="emit('close')">取消</Button>
      <Button variant="danger" :loading="busy" @click="emit('confirm')">确认删除</Button>
    </template>
  </Modal>
</template>
