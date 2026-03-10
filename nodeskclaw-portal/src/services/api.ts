import axios from 'axios'
import { getCurrentLocale } from '@/i18n'
import { useToast } from '@/composables/useToast'
import { i18n } from '@/i18n'

let lastBackendWarningAt = 0
const BACKEND_WARNING_COOLDOWN = 15_000

function notifyBackendUnavailable(status?: number) {
  const now = Date.now()
  if (now - lastBackendWarningAt < BACKEND_WARNING_COOLDOWN) return
  lastBackendWarningAt = now

  const { t } = i18n.global
  const toast = useToast()
  const key =
    status && status >= 502 && status <= 504
      ? 'errors.system.backend_starting'
      : 'errors.system.backend_unreachable'
  toast.warning(t(key), { duration: 6000 })
}

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('portal_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  config.headers['Accept-Language'] = getCurrentLocale()
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status

    if (!error.response || error.code === 'ERR_NETWORK' || error.code === 'ECONNABORTED') {
      notifyBackendUnavailable()
    } else if (status >= 502 && status <= 504) {
      notifyBackendUnavailable(status)
    }

    if (status === 401) {
      const url = error.config?.url || ''
      if (!url.includes('/auth/')) {
        localStorage.removeItem('portal_token')
        localStorage.removeItem('portal_refresh_token')
        if (window.location.pathname !== '/login') {
          window.location.href = '/login'
        }
      }
    }

    if (status === 403) {
      const detail = error.response?.data?.detail
      if (detail?.error_code === 40350 && window.location.pathname !== '/force-change-password') {
        window.location.href = '/force-change-password'
      }
    }

    return Promise.reject(error)
  },
)

export default api
