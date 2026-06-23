/**
 * API 信封：后端所有响应统一形如 { ok, message?, data?, ... }。
 */
export interface Envelope<T = unknown> {
  ok: boolean
  message?: string
  data?: T
  [key: string]: unknown
}
