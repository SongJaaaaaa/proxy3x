/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_TARGET?: string
}
interface ImportMeta {
  readonly env: ImportMetaEnv
}

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<Record<string, unknown>, Record<string, unknown>, unknown>
  export default component
}

declare module 'node:url' {
  export class URL {
    constructor(input: string, base?: string | URL)
  }
  export function fileURLToPath(url: string | URL): string
}

declare const process: {
  cwd(): string
}
