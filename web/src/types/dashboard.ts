/**
 * 后端 /api/dashboard payload 的客户端镜像。字段与 server/app.py 的
 * dashboard_data() / upstream_public() / package_usage() 严格对应。
 * 后端契约变更时，先改这里。
 */

/** 总览汇总卡片数据 */
export interface Summary {
  package_count: number
  upstream_count: number
  total_used_gb: number
  total_limit_gb: number
  residential_used_gb: number
}

/** 用户套餐（packages 表 + 实时用量） */
export interface Package {
  id: number
  name: string
  sub_id: string
  notes: string
  total_gb: number
  residential_gb: number
  total_bytes: number
  residential_bytes: number
  direct_used_gb: number
  residential_used_gb: number
  total_used_gb: number
  direct_port: number | null
  residential_port: number | null
  upstream_id: number | null
  direct_runtime_enabled: boolean
  residential_runtime_enabled: boolean
  enabled: boolean
  expired: boolean
  expires_at: number
  expires_at_text: string
  clash_url: string
  shadowrocket_url: string
  shadowrocket_alt_url: string
}

/** 家宽出口（upstreams 表 + 用量 + 额度，账号/密码已遮罩） */
export interface Upstream {
  id: number
  protocol: string
  host: string
  port: number
  username: string // 已遮罩
  password: string // 已遮罩
  remark: string
  assigned_to: string
  status: string // 可用 / 不可用 / 未检测
  last_error: string
  last_check_at: number
  used_bytes: number
  used_gb: number
  quota_gb: number // 0 = 未设额度
  quota_bytes: number
  usage_percent: number | null // null = 未设额度，前端不画进度
}

/** 家宽完整明文信息（/api/upstreams/{id}/reveal，账号密码未遮罩） */
export interface UpstreamReveal {
  id: number
  protocol: string
  host: string
  port: number
  username: string
  password: string
  remark: string
  assigned_to: string
  status: string
  uri: string // 拼好的连接串，如 socks5://user:pass@host:port
  line: string // IP:端口:账号:密码
}

/** 操作日志 */
export interface EventItem {
  id: number
  level: string // 信息 / 警告
  message: string
  created_at: number
}

/** /api/dashboard 完整返回 */
export interface DashboardData {
  summary: Summary
  packages: Package[]
  upstreams: Upstream[]
  events: EventItem[]
}

/** 新增用户入参 */
export interface CreatePackageBody {
  name: string
  sub_id: string
  total_gb: number
  residential_gb: number
  upstream_id?: number | null
  notes?: string
  expires_at?: string | number | null
}

/** 编辑用户入参 */
export interface UpdatePackageBody {
  name: string
  total_gb: number
  residential_gb: number
  notes?: string
  upstream_id?: number | null
  expires_at?: string | number | null
}

/** 新增家宽入参 */
export interface CreateUpstreamBody {
  line: string
  remark?: string
  assigned_to?: string
  quota_gb?: number
}

/** 编辑家宽入参 */
export interface UpdateUpstreamBody {
  remark?: string
  assigned_to?: string
  quota_gb?: number
}
