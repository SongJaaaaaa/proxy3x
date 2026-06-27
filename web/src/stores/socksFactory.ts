import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '@/api/endpoints'
import type { CreateSocksSourceBody, SocksEndpoint, SocksSource, UpdateSocksEndpointBody } from '@/types/dashboard'

export const useSocksFactoryStore = defineStore('socksFactory', () => {
  const sources = ref<SocksSource[]>([])
  const current = ref<SocksSource | null>(null)
  const loading = ref(false)

  const totalSources = computed(() => sources.value.length)
  const totalNodes = computed(() => sources.value.reduce((sum, s) => sum + Number(s.node_count || 0), 0))
  const totalEndpoints = computed(() => sources.value.reduce((sum, s) => sum + Number(s.endpoint_count || 0), 0))
  const activeEndpoints = computed(() =>
    sources.value.reduce((sum, s) => sum + s.endpoints.filter((e) => e.enabled && !e.expired).length, 0),
  )

  async function refreshList() {
    loading.value = true
    try {
      const r = await api.socksSources()
      sources.value = r.data || []
    } finally {
      loading.value = false
    }
  }

  async function loadSource(id: number) {
    loading.value = true
    try {
      const r = await api.socksSource(id)
      if (!r.data) throw new Error('订阅源不存在')
      current.value = r.data
      const idx = sources.value.findIndex((s) => s.id === id)
      if (idx >= 0) sources.value[idx] = r.data
      return r.data
    } finally {
      loading.value = false
    }
  }

  async function createSource(body: CreateSocksSourceBody) {
    const r = await api.createSocksSource(body)
    await refreshList()
    return r
  }

  async function updateSource(id: number, body: CreateSocksSourceBody) {
    const r = await api.updateSocksSource(id, body)
    await loadSource(id)
    await refreshList()
    return r
  }

  async function deleteSource(id: number) {
    const r = await api.deleteSocksSource(id)
    await refreshList()
    return r
  }

  async function refreshSource(id: number) {
    const r = await api.refreshSocksSource(id)
    await loadSource(id)
    await refreshList()
    return r
  }

  async function generateSource(id: number) {
    const r = await api.generateSocksSource(id)
    await loadSource(id)
    await refreshList()
    return r
  }

  async function toggleSource(id: number, enabled: boolean) {
    const r = await api.toggleSocksSource(id, enabled)
    await loadSource(id)
    await refreshList()
    return r
  }

  async function copySource(id: number) {
    const r = await api.copySocksSource(id)
    return r.data?.text || ''
  }

  async function syncUsage(id: number) {
    const r = await api.syncSocksUsage(id)
    await loadSource(id)
    await refreshList()
    return r
  }

  async function revealEndpoint(id: number): Promise<SocksEndpoint> {
    const r = await api.revealSocksEndpoint(id)
    if (!r.data) throw new Error('SOCKS5 不存在')
    return r.data
  }

  async function toggleEndpoint(id: number, enabled: boolean, sourceId: number) {
    const r = await api.toggleSocksEndpoint(id, enabled)
    await loadSource(sourceId)
    await refreshList()
    return r
  }

  async function updateEndpoint(id: number, body: UpdateSocksEndpointBody, sourceId: number) {
    const r = await api.updateSocksEndpoint(id, body)
    await loadSource(sourceId)
    await refreshList()
    return r
  }

  return {
    sources,
    current,
    loading,
    totalSources,
    totalNodes,
    totalEndpoints,
    activeEndpoints,
    refreshList,
    loadSource,
    createSource,
    updateSource,
    deleteSource,
    refreshSource,
    generateSource,
    toggleSource,
    copySource,
    syncUsage,
    revealEndpoint,
    toggleEndpoint,
    updateEndpoint,
  }
})
