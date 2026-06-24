import { ref, computed, watch } from 'vue'

/**
 * useTheme —— 全局明暗主题（暗夜/白天）。
 * - 单例 ref：所有组件共享同一份状态，任意处切换全局生效。
 * - 通过给 <html> 增删 .dark 类驱动 Tailwind 的 class 暗色策略与 CSS 变量。
 * - 选择持久化到 localStorage，刷新后保留；默认暗夜（与原 UI 一致）。
 * - 首屏防闪烁由 index.html 内联脚本先行处理，这里负责后续响应式切换与持久化。
 */
export type Theme = 'dark' | 'light'

const STORAGE_KEY = 'proxy3x-theme'

function getInitial(): Theme {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved === 'light' || saved === 'dark') return saved
  } catch {
    /* localStorage 不可用时忽略 */
  }
  return 'dark' // 默认暗夜
}

function apply(theme: Theme) {
  const root = document.documentElement
  root.dataset.theme = theme
  if (theme === 'dark') {
    root.classList.add('dark')
  } else {
    root.classList.remove('dark')
  }
}

// 模块级单例：整个应用共享同一个 theme 状态
const theme = ref<Theme>(getInitial())

watch(
  theme,
  (value) => {
    apply(value)
    try {
      localStorage.setItem(STORAGE_KEY, value)
    } catch {
      /* 忽略写入失败 */
    }
  },
  { immediate: true },
)

export function useTheme() {
  const isDark = computed(() => theme.value === 'dark')

  function setTheme(value: Theme) {
    theme.value = value
  }

  function toggle() {
    theme.value = theme.value === 'dark' ? 'light' : 'dark'
  }

  return { theme, isDark, setTheme, toggle }
}
