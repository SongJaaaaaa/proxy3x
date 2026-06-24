import { http } from './client'
import type {
  CreatePackageBody,
  CreateUpstreamBody,
  DashboardData,
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
  deleteUpstream: (id: number) => http.del(`/upstreams/${id}`),
}
