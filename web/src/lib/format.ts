/**
 * 展示层格式化工具。后端用量字段统一是 GB（number），这里只负责显示。
 * 不放业务逻辑，纯函数。
 */

/** 把 GB 数值格式化为带单位字符串，如 32.1 -> "32.1 GB"。 */
export function gb(value: number | null | undefined, digits = 1): string {
  const n = Number(value ?? 0)
  if (!Number.isFinite(n)) return '0 GB'
  return `${n.toFixed(digits)} GB`
}

/** 字节/秒转速度展示。0/空表示还没测速。 */
export function speed(value: number | null | undefined): string {
  const n = Number(value ?? 0)
  if (!Number.isFinite(n) || n <= 0) return '未测速'
  if (n >= 1024 * 1024) return `${(n / 1024 / 1024).toFixed(2)} MB/s`
  return `${(n / 1024).toFixed(1)} KB/s`
}

/**
 * 用量百分比（0-100，封顶 100）。quota<=0 视为未设额度，返回 null。
 * 与后端 usage_percent 语义一致，前端也可本地再算一遍。
 */
export function percent(used: number, total: number): number | null {
  if (!total || total <= 0) return null
  return Math.min(100, Math.round((used / total) * 1000) / 10)
}

/** 进度条颜色：按占比给绿/黄/红，>=100% 用 destructive。 */
export function usageTone(pct: number | null): 'green' | 'amber' | 'red' | 'muted' {
  if (pct === null) return 'muted'
  if (pct >= 100) return 'red'
  if (pct >= 80) return 'amber'
  return 'green'
}

/** Unix 秒时间戳转本地可读时间。0/空返回占位。 */
export function fromUnix(seconds: number | null | undefined): string {
  const s = Number(seconds ?? 0)
  if (!s) return '—'
  return new Date(s * 1000).toLocaleString('zh-CN', { hour12: false })
}

/**
 * 返回 N 个月后的 datetime-local 字符串（YYYY-MM-DDTHH:mm），用于表单默认到期时间。
 */
export function monthsFromNowLocal(months = 1): string {
  const d = new Date()
  d.setMonth(d.getMonth() + months)
  return toLocalInput(d)
}

/**
 * 把 Date 格式化为 datetime-local 输入需要的 'YYYY-MM-DDTHH:mm'（本地时区）。
 */
function toLocalInput(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/**
 * Unix 秒时间戳转 datetime-local 字符串（'YYYY-MM-DDTHH:mm'）。
 * 0/空返回 ''，供编辑表单回填已有到期时间（留空表示永久有效）。
 */
export function unixToLocalInput(seconds: number | null | undefined): string {
  const s = Number(seconds ?? 0)
  if (!s) return ''
  return toLocalInput(new Date(s * 1000))
}
