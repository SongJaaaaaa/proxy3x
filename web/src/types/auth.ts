/** 登录入参 */
export interface LoginPayload {
  username: string
  password: string
}

/** /api/me 返回 */
export interface MeResponse {
  ok: boolean
  username?: string | null
}
