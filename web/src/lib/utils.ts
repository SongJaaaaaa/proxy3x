import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

/**
 * cn —— 合并 Tailwind class，处理条件类名与冲突覆盖（shadcn 标准工具）。
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
