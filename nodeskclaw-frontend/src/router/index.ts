import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { usePermissions } from '@/composables/usePermissions'
import { eeAdminRoutes } from '@/router/ee-stub'

declare module 'vue-router' {
  interface RouteMeta {
    requiresAuth?: boolean
    minRole?: string
    requireFeature?: string
  }
}

const ceRoutes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/login/callback/:provider',
    name: 'OAuthCallback',
    component: () => import('@/views/OAuthCallback.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/no-access',
    name: 'NoAccess',
    component: () => import('@/views/NoAccess.vue'),
  },
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('@/views/Dashboard/index.vue'),
    meta: { minRole: 'member' },
  },
  {
    path: '/instances',
    name: 'Instances',
    component: () => import('@/views/Instances/index.vue'),
    meta: { minRole: 'member' },
  },
  {
    path: '/instances/:id',
    name: 'InstanceDetail',
    component: () => import('@/views/Instances/Detail.vue'),
    meta: { minRole: 'member' },
  },
  {
    path: '/deploy',
    name: 'Deploy',
    component: () => import('@/views/Deploy/index.vue'),
    meta: { minRole: 'operator' },
  },
  {
    path: '/deploy/progress/:deployId',
    name: 'DeployProgress',
    component: () => import('@/views/Deploy/DeployProgress.vue'),
    meta: { minRole: 'operator' },
  },
  {
    path: '/instances/:id/logs',
    name: 'Logs',
    component: () => import('@/views/Logs/index.vue'),
    meta: { minRole: 'member' },
  },
  {
    path: '/instances/:id/monitor',
    name: 'Monitor',
    component: () => import('@/views/Monitor/index.vue'),
    meta: { minRole: 'member' },
  },
  {
    path: '/instances/:id/history',
    name: 'History',
    component: () => import('@/views/History/index.vue'),
    meta: { minRole: 'member' },
  },
  {
    path: '/events',
    name: 'Events',
    component: () => import('@/views/Events/index.vue'),
    meta: { minRole: 'member' },
  },
  {
    path: '/cluster',
    name: 'Cluster',
    component: () => import('@/views/Cluster/index.vue'),
    meta: { minRole: 'admin' },
  },
  {
    path: '/cluster/:id',
    name: 'ClusterDetail',
    component: () => import('@/views/Cluster/Detail.vue'),
    meta: { minRole: 'admin' },
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/Settings/index.vue'),
    meta: { minRole: 'admin' },
  },
  {
    path: '/gene',
    name: 'Gene',
    component: () => import('@/views/Gene/index.vue'),
    meta: { minRole: 'admin' },
  },
  {
    path: '/akr-summary',
    name: 'AkrSummary',
    component: () => import('@/views/AkrSummary/index.vue'),
    meta: { minRole: 'admin' },
  },
]

const routes: RouteRecordRaw[] = [...ceRoutes, ...eeAdminRoutes]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to, _from, next) => {
  const token = localStorage.getItem('token')
  const isLoginPage = to.path === '/login' || to.path.startsWith('/login/callback/')

  if (isLoginPage) {
    return next()
  }

  if (!token && to.meta.requiresAuth !== false) {
    return next('/login')
  }

  const auth = useAuthStore()
  if (!auth.systemInfo) {
    await auth.fetchSystemInfo()
  }
  if (token && !auth.user) {
    await auth.fetchUser()
  }

  if (!auth.user) {
    return next('/login')
  }

  const { canAccessRoute, hasAdminAccess } = usePermissions()

  if (to.path !== '/no-access' && !hasAdminAccess.value) {
    return next('/no-access')
  }

  const minRole = to.meta.minRole
  if (minRole && !canAccessRoute(minRole)) {
    return next('/no-access')
  }

  const requiredFeature = to.meta.requireFeature
  if (requiredFeature && auth.systemInfo) {
    const feat = auth.systemInfo.features.find((f: any) => f.id === requiredFeature)
    if (!feat?.enabled) {
      return next('/no-access')
    }
  }

  next()
})

export default router
