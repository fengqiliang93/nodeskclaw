import { ref } from 'vue'

export type NotifyType = 'success' | 'error' | 'info' | 'warning'

export interface NotifyAction {
  label: string
  onClick: () => void
}

export interface NotifyOptions {
  action?: NotifyAction
  duration?: number
}

export interface NotifyItem {
  id: number
  type: NotifyType
  message: string
  action?: NotifyAction
  leaving: boolean
}

const queue = ref<NotifyItem[]>([])
let nextId = 0

function push(type: NotifyType, message: string, options?: NotifyOptions) {
  const id = nextId++
  queue.value.push({ id, message, type, action: options?.action, leaving: false })
  setTimeout(() => {
    dismiss(id)
  }, options?.duration ?? 3000)
}

function dismiss(id: number) {
  const item = queue.value.find(n => n.id === id)
  if (!item) return
  item.leaving = true
  setTimeout(() => {
    queue.value = queue.value.filter(n => n.id !== id)
  }, 300)
}

export function useNotify() {
  return {
    queue,
    dismiss,
    success: (message: string, options?: NotifyOptions) => push('success', message, options),
    error: (message: string, options?: NotifyOptions) => push('error', message, options),
    info: (message: string, options?: NotifyOptions) => push('info', message, options),
    warning: (message: string, options?: NotifyOptions) => push('warning', message, options),
  }
}
