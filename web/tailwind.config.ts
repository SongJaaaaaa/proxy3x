import type { Config } from 'tailwindcss'
import animate from 'tailwindcss-animate'

// 颜色统一走 CSS 变量。使用 Tailwind 官方的 <alpha-value> 写法，
// 避免 dev server / build 把主题色提前编译成某一套固定 RGB。
const v = (name: string) => `rgb(var(${name}) / <alpha-value>)`

export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{vue,ts}'],
  theme: {
    extend: {
      colors: {
        'on-primary': v('--c-on-primary'),
        background: v('--c-background'),
        'secondary-fixed': v('--c-secondary-fixed'),
        'secondary-fixed-dim': v('--c-secondary-fixed-dim'),
        outline: v('--c-outline'),
        'outline-variant': v('--c-outline-variant'),
        'tertiary-container': v('--c-tertiary-container'),
        'on-tertiary-container': v('--c-on-tertiary-container'),
        primary: v('--c-primary'),
        'primary-container': v('--c-primary-container'),
        'on-primary-container': v('--c-on-primary-container'),
        'surface-dim': v('--c-surface-dim'),
        'surface': v('--c-surface'),
        'surface-bright': v('--c-surface-bright'),
        'surface-variant': v('--c-surface-variant'),
        'surface-container-lowest': v('--c-surface-container-lowest'),
        'surface-container-low': v('--c-surface-container-low'),
        'surface-container': v('--c-surface-container'),
        'surface-container-high': v('--c-surface-container-high'),
        'surface-container-highest': v('--c-surface-container-highest'),
        'on-surface': v('--c-on-surface'),
        'on-surface-variant': v('--c-on-surface-variant'),
        'on-background': v('--c-on-background'),
        error: v('--c-error'),
        'error-container': v('--c-error-container'),
        'on-error': v('--c-on-error'),
        'on-error-container': v('--c-on-error-container'),
        tertiary: v('--c-tertiary'),
        secondary: v('--c-secondary'),
      },
      borderRadius: {
        DEFAULT: '0.25rem',
        lg: '0.5rem',
        xl: '0.75rem',
        full: '9999px',
      },
      spacing: {
        'panel-gap': '20px',
        'stack-tight': '8px',
        gutter: '16px',
        unit: '4px',
        'container-padding': '24px',
      },
      fontFamily: {
        sans: ['Inter', 'PingFang SC', 'Microsoft YaHei', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
      },
      fontSize: {
        'body-md': ['14px', { lineHeight: '22px', fontWeight: '400' }],
        'code-xs': ['12px', { lineHeight: '16px', fontWeight: '400' }],
        'display-lg': ['32px', { lineHeight: '40px', letterSpacing: '-0.02em', fontWeight: '700' }],
        'title-sm': ['18px', { lineHeight: '24px', fontWeight: '600' }],
        'label-sm': ['12px', { lineHeight: '16px', letterSpacing: '0.05em', fontWeight: '500' }],
        'headline-md': ['24px', { lineHeight: '32px', fontWeight: '600' }],
      },
    },
  },
  plugins: [animate],
} satisfies Config
