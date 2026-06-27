<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import Modal from '@/components/ui/Modal.vue'
import Field from '@/components/ui/Field.vue'
import Button from '@/components/ui/Button.vue'
import { unixToLocalInput } from '@/lib/format'
import type { SocksEndpoint } from '@/types/dashboard'

const props = defineProps<{ open: boolean; item?: SocksEndpoint | null; busy?: boolean }>()
const emit = defineEmits<{
  close: []
  submit: [payload: { quota_gb: number; expires_at: string; remark: string }]
}>()

const form = reactive({ quota_gb: 0, expires_at: '', remark: '' })
const error = ref('')

watch(
  () => [props.open, props.item] as const,
  () => {
    error.value = ''
    form.quota_gb = Number(props.item?.quota_gb || 0)
    form.expires_at = unixToLocalInput(props.item?.expires_at)
    form.remark = props.item?.remark || props.item?.node_name || ''
  },
  { immediate: true },
)

function setError(msg: string) {
  error.value = msg
}

function submit() {
  emit('submit', {
    quota_gb: Number(form.quota_gb) || 0,
    expires_at: form.expires_at,
    remark: form.remark.trim(),
  })
}

defineExpose({ setError })
</script>

<template>
  <Modal :open="open" title="设置 SOCKS5" icon="tune" icon-tone="green" @close="emit('close')">
    <div v-if="error" class="rounded-lg border border-error/30 bg-error/10 px-3 py-2 text-sm text-error">
      {{ error }}
    </div>
    <div class="rounded-lg border border-outline-variant/30 bg-surface-container-lowest/60 p-3">
      <p class="font-label-sm text-label-sm text-on-surface">{{ item?.node_name || item?.remark }}</p>
      <p class="mt-1 font-code-xs text-[11px] text-outline">{{ item?.protocol }} · {{ item?.server }}:{{ item?.node_port }}</p>
    </div>
    <Field label="备注">
      <input v-model="form.remark" class="control" placeholder="给这个 socks5 取个好认的名字" />
    </Field>
    <Field label="流量额度" hint="GB，0=不限制">
      <input v-model.number="form.quota_gb" type="number" min="0" step="1" class="control" />
    </Field>
    <Field label="到期时间">
      <input v-model="form.expires_at" type="datetime-local" class="control" />
    </Field>
    <template #footer>
      <Button variant="subtle" @click="emit('close')">取消</Button>
      <Button variant="primary" :loading="busy" @click="submit">保存</Button>
    </template>
  </Modal>
</template>
