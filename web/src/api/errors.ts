/**
 * ApiError —— 后端返回 ok:false 或 HTTP 非 2xx 时抛出。
 * status 为 HTTP 状态码（用于 401 跳登录判断）。
 */
export class ApiError extends Error {
  status: number
  constructor(message: string, status = 0) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}
