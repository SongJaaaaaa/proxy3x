import type { Envelope } from '@/types/api'
import { ApiError } from './errors'

/**
 * 唯一的 HTTP 出口。约定：
 * - 路径前缀 /api，credentials:'include' 携带 HttpOnly 会话 cookie。
 * - 解析 { ok, message, data } 信封；ok===false 或非 2xx 抛 ApiError。
 * - HTTP 401 触发 onUnauthorized（路由层注册 → 跳登录）。
 * 业务代码不直接 fetch，统一走 endpoints.ts。
 */

let onUnauthorized: (() => void) | null = null

/** 注册 401 处理钩子（在 router 初始化时调用）。 */
export function setUnauthorizedHandler(fn: () => void) {
  onUnauthorized = fn
}

async function request<T>(path: string, init: RequestInit = {}): Promise<Envelope<T>> {
  const headers: Record<string, string> = { ...(init.headers as Record<string, string>) }
  if (init.body && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json'
  }

  let resp: Response
  try {
    resp = await fetch(`/api${path}`, { ...init, headers, credentials: 'include' })
  } catch {
    throw new ApiError('网络错误，无法连接服务器', 0)
  }

  if (resp.status === 401) {
    onUnauthorized?.()
    throw new ApiError('请先登录', 401)
  }

  let payload: Envelope<T>
  try {
    payload = (await resp.json()) as Envelope<T>
  } catch {
    throw new ApiError(`服务器返回异常（${resp.status}）`, resp.status)
  }

  if (!resp.ok || payload.ok === false) {
    throw new ApiError(payload.message || `请求失败（${resp.status}）`, resp.status)
  }
  return payload
}

export const http = {
  get: <T>(path: string) => request<T>(path, { method: 'GET' }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PUT', body: body ? JSON.stringify(body) : undefined }),
  del: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
}
