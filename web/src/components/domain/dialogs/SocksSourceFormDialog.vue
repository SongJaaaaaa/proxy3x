<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import Modal from '@/components/ui/Modal.vue'
import Field from '@/components/ui/Field.vue'
import Button from '@/components/ui/Button.vue'
import { monthsFromNowLocal } from '@/lib/format'
import type { SocksSource } from '@/types/dashboard'

const props = defineProps<{ open: boolean; editing?: SocksSource | null; busy?: boolean }>()
const emit = defineEmits<{
  close: []
  submit: [payload: { name: string; url: string; expires_at: string }]
}>()

const form = reactive({ name: '', url: '', expires_at: monthsFromNowLocal() })
const error = ref('')

watch(
  () => [props.open, props.editing] as const,
  () => {
    error.value = ''
    form.name = props.editing?.name || ''
    form.url = props.editing?.url || ''
    form.expires_at = props.editing ? '' : monthsFromNowLocal()
  },
  { immediate: true },
)

function setError(msg: string) {
  error.value = msg
}

function submit() {
  if (!form.name.trim() || !form.url.trim()) {
    error.value = '名称和订阅链接不能为空'
    return
  }
  emit('submit', {
    name: form.name.trim(),
    url: form.url.trim(),
    expires_at: form.expires_at,
  })
}

defineExpose({ setError })
</script>

<template>
  <Modal
    :open="open"
    :title="editing ? '编辑订阅源' : '添加订阅源'"
    icon="hub"
    icon-tone="purple"
    @close="emit('close')"
  >
    <div v-if="error" class="rounded-lg border border-error/30 bg-error/10 px-3 py-2 text-sm text-error">
      {{ error }}
    </div>
    <Field label="名称" required>
      <input v-model="form.name" class="control" placeholder="例如：proxyinfo 主订阅" />
    </Field>
    <Field label="订阅链接" required>
      <textarea v-model="form.url" class="control min-h-[92px]" placeholder="https://example.com/api/v1/client/subscribe?token=..." />
    </Field>
    <Field v-if="!editing" label="SOCKS5 到期时间" hint="默认一个月后，可自行选择">
      <input v-model="form.expires_at" type="datetime-local" class="control" />
    </Field>
    <div class="rounded-lg bg-surface-container-lowest/60 border border-outline-variant/30 p-3 text-sm text-on-surface-variant">
      刷新时会自动读取订阅响应里的流量限制；没有流量限制就按不限处理。生成时会按解析出的节点数量平均分配额度，默认到期时间为一个月。
    </div>
    <template #footer>
      <Button variant="subtle" @click="emit('close')">取消</Button>
      <Button variant="primary" :loading="busy" @click="submit">{{ editing ? '保存' : '添加并解析' }}</Button>
    </template>
  </Modal>
</template>
