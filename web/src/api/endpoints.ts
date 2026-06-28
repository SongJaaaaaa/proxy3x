import { http } from './client'
import type {
  CreatePackageBody,
  CreateSocksSourceBody,
  CreateUpstreamBody,
  DashboardData,
  SocksEndpoint,
  SocksSource,
  UpdateSocksEndpointBody,
  UpdatePackageBody,
  UpdateUpstreamBody,
  UpstreamReveal,
} from '@/types/dashboard'
import type { LoginPayload, MeResponse } from '@/types/auth'

/**
 * 后端契约的唯一落点 —— 每个函数对应 server/app.py 的一条路由。
 * 契约变更只需改这里 + types/。
 */
export const api = {
  // —— 鉴权 ——
  login: (body: LoginPayload) => http.post('/login', body),
  logout: () => http.post('/logout'),
  me: () => http.get<never>('/me') as unknown as Promise<MeResponse>,

  // —— 总览 ——
  dashboard: () => http.get<DashboardData>('/dashboard'),
  enforce: () => http.post('/enforce'),
  regenerate: () => http.post('/regenerate'),

  // —— 用户套餐 ——
  createPackage: (body: CreatePackageBody) => http.post<{ id: number }>('/packages', body),
  updatePackage: (id: number, body: UpdatePackageBody) => http.put(`/packages/${id}`, body),
  deletePackage: (id: number) => http.del(`/packages/${id}`),
  ensureResidential: (id: number) => http.post(`/packages/${id}/residential`),
  syncPackage: (id: number) => http.post(`/packages/${id}/sync`),

  // —— SOCKS5 上游 ——
  createUpstream: (body: CreateUpstreamBody) => http.post('/upstreams', body),
  revealUpstream: (id: number) => http.get<UpstreamReveal>(`/upstreams/${id}/reveal`),
  updateUpstream: (id: number, body: UpdateUpstreamBody) => http.put(`/upstreams/${id}`, body),
  checkUpstream: (id: number) => http.post(`/upstreams/${id}/check`),
  speedTestUpstream: (id: number) => http.post<{ speed_bps: number }>(`/upstreams/${id}/speed-test`),
  deleteUpstream: (id: number) => http.del(`/upstreams/${id}`),

  // —— 订阅 SOCKS 工厂 ——
  socksSources: () => http.get<SocksSource[]>('/socks-sources'),
  socksSource: (id: number) => http.get<SocksSource>(`/socks-sources/${id}`),
  createSocksSource: (body: CreateSocksSourceBody) => http.post<{ id: number }>('/socks-sources', body),
  updateSocksSource: (id: number, body: CreateSocksSourceBody) => http.put(`/socks-sources/${id}`, body),
  deleteSocksSource: (id: number) => http.del(`/socks-sources/${id}`),
  refreshSocksSource: (id: number) => http.post(`/socks-sources/${id}/refresh`),
  generateSocksSource: (id: number, body: { expires_at?: string | number | null } = {}) => http.post(`/socks-sources/${id}/generate`, body),
  toggleSocksSource: (id: number, enabled: boolean) => http.post(`/socks-sources/${id}/toggle`, { enabled }),
  copySocksSource: (id: number) => http.post<{ text: string }>(`/socks-sources/${id}/copy`),
  syncSocksUsage: (id: number) => http.post(`/socks-sources/${id}/sync-usage`),
  revealSocksEndpoint: (id: number) => http.post<SocksEndpoint>(`/socks-endpoints/${id}/reveal`),
  toggleSocksEndpoint: (id: number, enabled: boolean) => http.post(`/socks-endpoints/${id}/toggle`, { enabled }),
  speedTestSocksEndpoint: (id: number) => http.post<{ speed_bps: number }>(`/socks-endpoints/${id}/speed-test`),
  updateSocksEndpoint: (id: number, body: UpdateSocksEndpointBody) => http.put(`/socks-endpoints/${id}`, body),
}
