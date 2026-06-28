<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import Modal from '@/components/ui/Modal.vue'
import Field from '@/components/ui/Field.vue'
import Button from '@/components/ui/Button.vue'
import { monthsFromNowLocal } from '@/lib/format'
import type { SocksSource, Upstream } from '@/types/dashboard'

const props = defineProps<{ open: boolean; editing?: SocksSource | null; upstreams?: Upstream[]; busy?: boolean }>()
const emit = defineEmits<{
  close: []
  submit: [payload: { name: string; url: string; relay_upstream_id: number | null; expires_at: string }]
}>()

const form = reactive({ name: '', url: '', relay_upstream_id: 0, expires_at: monthsFromNowLocal() })
const error = ref('')
const relayOptions = computed(() => (props.upstreams || []).filter((u) => !u.expired))

function relayLabel(u: Upstream) {
  const node = u.source_node_name ? ` / ${u.source_node_name}` : ''
  return `${u.socks5_name || u.remark || u.host}${node}（${u.status || '未检测'}）`
}

watch(
  () => [props.open, props.editing] as const,
  () => {
    error.value = ''
    form.name = props.editing?.name || ''
    form.url = props.editing?.url || ''
    form.relay_upstream_id = props.editing?.relay_upstream_id || 0
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
    relay_upstream_id: Number(form.relay_upstream_id) || null,
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
    <Field label="中转 SOCKS5" hint="订阅内节点在服务器直连不通时，可统一通过这里选择的 SOCKS5 再连接上游">
      <select v-model.number="form.relay_upstream_id" class="control">
        <option :value="0">不中转，服务器直连订阅节点</option>
        <option v-for="u in relayOptions" :key="u.id" :value="u.id">
          {{ relayLabel(u) }}
        </option>
      </select>
    </Field>
    <Field v-if="!editing" label="SOCKS5 到期时间" hint="默认一个月后，可自行选择">
      <input v-model="form.expires_at" type="datetime-local" class="control" />
    </Field>
    <div class="rounded-lg bg-surface-container-lowest/60 border border-outline-variant/30 p-3 text-sm text-on-surface-variant">
      刷新时会自动读取订阅响应里的流量限制；没有流量限制就按不限处理。设置中转后，该订阅生成的 SOCKS5 会统一先走中转 SOCKS5。
    </div>
    <template #footer>
      <Button variant="subtle" @click="emit('close')">取消</Button>
      <Button variant="primary" :loading="busy" @click="submit">{{ editing ? '保存' : '添加并解析' }}</Button>
    </template>
  </Modal>
</template>
