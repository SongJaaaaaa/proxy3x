import { onMounted, onUnmounted } from 'vue'

/**
 * usePolling —— 定时执行 fn；标签页隐藏时暂停，可见时立即补一次并恢复。
 * 用于 DashboardView 周期刷新；组件卸载自动清理。
 */
export function usePolling(fn: () => void | Promise<void>, intervalMs: number) {
  let timer: ReturnType<typeof setInterval> | null = null

  function tick() {
    if (!document.hidden) void fn()
  }
  function start() {
    if (timer) return
    timer = setInterval(tick, intervalMs)
  }
  function stop() {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }
  function onVisibility() {
    if (document.hidden) {
      stop()
    } else {
      void fn()
      start()
    }
  }

  onMounted(() => {
    void fn()
    start()
    document.addEventListener('visibilitychange', onVisibility)
  })
  onUnmounted(() => {
    stop()
    document.removeEventListener('visibilitychange', onVisibility)
  })

  return { start, stop }
}
