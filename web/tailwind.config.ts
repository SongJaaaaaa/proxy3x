import type { Config } from 'tailwindcss'
import animate from 'tailwindcss-animate'

// proxy3x 暗色科技主题 —— 与 stitch 生成 UI（Cyber-Proxy Management）同款 token。
// 颜色直接采用 stitch DESIGN.md 的 Material 命名，方便 1:1 还原参考图的 class。
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{vue,ts}'],
  theme: {
    extend: {
      colors: {
        'on-primary': '#002b75',
        background: '#0f141b',
        'secondary-fixed': '#24ffcd',
        'secondary-fixed-dim': '#00e0b3',
        outline: '#8c90a1',
        'outline-variant': '#424656',
        'tertiary-container': '#a32bff',
        'on-tertiary-container': '#fff5ff',
        primary: '#b3c5ff',
        'primary-container': '#0066ff',
        'on-primary-container': '#f8f7ff',
        'surface-dim': '#0f141b',
        'surface': '#0f141b',
        'surface-bright': '#353941',
        'surface-variant': '#31353d',
        'surface-container-lowest': '#0a0e15',
        'surface-container-low': '#181c23',
        'surface-container': '#1c2027',
        'surface-container-high': '#262a32',
        'surface-container-highest': '#31353d',
        'on-surface': '#dfe2ed',
        'on-surface-variant': '#c2c6d8',
        'on-background': '#dfe2ed',
        error: '#ffb4ab',
        'error-container': '#93000a',
        'on-error': '#690005',
        'on-error-container': '#ffdad6',
        tertiary: '#dfb7ff',
        secondary: '#ffffff',
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
