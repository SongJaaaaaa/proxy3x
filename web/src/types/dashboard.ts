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
export interface PackageBinding {
  id: number
  upstream_id: number
  display_name: string
  port: number | null
  email: string
  sort_order: number
  enabled: boolean
}

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
  upstream_ids: number[]
  fallback_policy: 'block' | 'auto' | 'direct'
  bindings: PackageBinding[]
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

/** SOCKS5 上游（upstreams 表 + 用量 + 额度，账号/密码已遮罩） */
export interface Upstream {
  id: number
  protocol: string
  host: string
  port: number
  username: string // 已遮罩
  password: string // 已遮罩
  remark: string
  display_name: string
  socks5_name: string
  source_node_name: string
  assigned_to: string
  status: string // 可用 / 不可用 / 未检测
  last_error: string
  last_check_at: number
  latency_ms: number
  speed_bps: number
  last_speed_at: number
  used_bytes: number
  used_gb: number
  quota_gb: number // 0 = 未设额度
  quota_bytes: number
  usage_percent: number | null // null = 未设额度，前端不画进度
  expired: boolean
  expires_at: number
  expires_at_text: string
}

/** SOCKS5 完整明文信息（/api/upstreams/{id}/reveal，账号密码未遮罩） */
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
  expires_at: number
  expires_at_text: string
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

export interface SocksNode {
  id: number
  source_id: number
  node_key: string
  name: string
  protocol: string
  server: string
  port: number
  status: string
  last_error: string
  latency_ms: number
  speed_bps: number
  last_speed_at: number
  created_at: number
  updated_at: number
}

export interface SocksEndpoint {
  id: number
  source_id: number
  node_id: number
  listen_port: number
  username: string
  password: string
  quota_gb: number
  quota_bytes: number
  upload_bytes: number
  download_bytes: number
  status: string
  last_error: string
  latency_ms: number
  speed_bps: number
  last_speed_at: number
  used_bytes: number
  used_gb: number
  usage_percent: number | null
  enabled: number
  expired: boolean
  expires_at: number
  expires_at_text: string
  remark: string
  node_name: string
  protocol: string
  server: string
  node_port: number
  uri: string
}

export interface SocksSource {
  id: number
  name: string
  url: string
  relay_upstream_id: number | null
  total_gb: number
  enabled: number
  node_count: number
  endpoint_count: number
  last_refresh_at: number
  last_error: string
  created_at: number
  updated_at: number
  used_bytes: number
  used_gb: number
  endpoint_quota_bytes: number
  endpoint_quota_gb: number
  usage_percent: number | null
  relay: {
    id: number | null
    name: string
    status: string
  }
  detail_url: string
  nodes: SocksNode[]
  endpoints: SocksEndpoint[]
}

export interface CreateSocksSourceBody {
  name: string
  url: string
  relay_upstream_id?: number | null
  total_gb?: number
  expires_at?: string | number | null
}

export interface UpdateSocksEndpointBody {
  quota_gb?: number
  expires_at?: string | number | null
  remark?: string
}

/** 新增用户入参 */
export interface CreatePackageBody {
  name: string
  sub_id: string
  total_gb: number
  residential_gb: number
  upstream_id?: number | null
  upstream_ids?: number[]
  fallback_policy?: 'block' | 'auto' | 'direct'
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
  upstream_ids?: number[]
  fallback_policy?: 'block' | 'auto' | 'direct'
  expires_at?: string | number | null
}

/** 新增 SOCKS5 入参 */
export interface CreateUpstreamBody {
  line: string
  remark?: string
  assigned_to?: string
  quota_gb?: number
  expires_at?: string | number | null
}

/** 编辑 SOCKS5 入参 */
export interface UpdateUpstreamBody {
  remark?: string
  assigned_to?: string
  quota_gb?: number
  expires_at?: string | number | null
}
