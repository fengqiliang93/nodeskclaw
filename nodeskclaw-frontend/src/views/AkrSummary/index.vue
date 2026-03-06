<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { BarChart3, Target, TrendingUp, Zap, RefreshCw, Loader2 } from 'lucide-vue-next'
import api from '@/services/api'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const loading = ref(false)
const data = ref<{ workspaces: WorkspaceSummary[] } | null>(null)

interface ObjectiveSummary {
  id: string
  title: string
  progress: number
  kr_count: number
}

interface WorkspaceSummary {
  workspace_id: string
  workspace_name: string
  objectives: ObjectiveSummary[]
  total_tasks: number
  completed_tasks: number
  completion_rate: number
  total_value: number
  total_tokens: number
  roi_per_1k_tokens: number
}

const orgId = computed(() => authStore.user?.current_org_id || '')

async function loadSummary() {
  if (!orgId.value) return
  loading.value = true
  try {
    const res = await api.get(`/orgs/${orgId.value}/akr-summary`)
    data.value = res.data.data
  } catch {
    data.value = null
  } finally {
    loading.value = false
  }
}

const totals = computed(() => {
  if (!data.value) return { tasks: 0, done: 0, value: 0, tokens: 0, roi: 0, rate: 0 }
  const ws = data.value.workspaces
  const tasks = ws.reduce((s, w) => s + w.total_tasks, 0)
  const done = ws.reduce((s, w) => s + w.completed_tasks, 0)
  const value = ws.reduce((s, w) => s + w.total_value, 0)
  const tokens = ws.reduce((s, w) => s + w.total_tokens, 0)
  const roi = tokens > 0 ? value / tokens * 1000 : 0
  const rate = tasks > 0 ? done / tasks : 0
  return { tasks, done, value, tokens, roi, rate }
})

function fmt(n: number, d = 2): string {
  return n.toLocaleString('zh-CN', { maximumFractionDigits: d })
}

function pct(n: number): string {
  return (n * 100).toFixed(1) + '%'
}

onMounted(loadSummary)
</script>

<template>
  <div class="max-w-6xl mx-auto px-6 py-8 space-y-8">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-xl font-bold">AKR 汇总</h1>
        <p class="text-sm text-muted-foreground mt-1">组织级目标 / 关键结果 / 任务全景</p>
      </div>
      <button
        class="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg border border-border hover:bg-muted transition-colors"
        :disabled="loading"
        @click="loadSummary"
      >
        <Loader2 v-if="loading" class="w-4 h-4 animate-spin" />
        <RefreshCw v-else class="w-4 h-4" />
        刷新
      </button>
    </div>

    <div v-if="loading && !data" class="flex justify-center py-16">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <template v-else-if="data">
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div class="p-4 rounded-xl bg-card border border-border space-y-1">
          <div class="flex items-center gap-1.5 text-muted-foreground text-xs">
            <Target class="w-3.5 h-3.5" />
            任务完成率
          </div>
          <div class="text-2xl font-bold">{{ pct(totals.rate) }}</div>
          <div class="text-xs text-muted-foreground">{{ totals.done }} / {{ totals.tasks }}</div>
        </div>

        <div class="p-4 rounded-xl bg-card border border-border space-y-1">
          <div class="flex items-center gap-1.5 text-muted-foreground text-xs">
            <TrendingUp class="w-3.5 h-3.5" />
            创造总价值
          </div>
          <div class="text-2xl font-bold">{{ fmt(totals.value) }}</div>
        </div>

        <div class="p-4 rounded-xl bg-card border border-border space-y-1">
          <div class="flex items-center gap-1.5 text-muted-foreground text-xs">
            <Zap class="w-3.5 h-3.5" />
            Token 总消耗
          </div>
          <div class="text-2xl font-bold">{{ fmt(totals.tokens, 0) }}</div>
        </div>

        <div class="p-4 rounded-xl bg-card border border-border space-y-1">
          <div class="flex items-center gap-1.5 text-muted-foreground text-xs">
            <BarChart3 class="w-3.5 h-3.5" />
            每千 Token 产出
          </div>
          <div class="text-2xl font-bold">{{ fmt(totals.roi) }}</div>
        </div>
      </div>

      <div class="space-y-4">
        <h2 class="text-lg font-semibold">各办公室概览</h2>

        <div v-if="data.workspaces.length === 0" class="text-sm text-muted-foreground py-8 text-center">
          暂无办公室数据
        </div>

        <div
          v-for="ws in data.workspaces"
          :key="ws.workspace_id"
          class="p-5 rounded-xl bg-card border border-border space-y-4"
        >
          <div class="flex items-center justify-between">
            <h3 class="font-medium text-base">{{ ws.workspace_name }}</h3>
            <div class="flex items-center gap-4 text-xs text-muted-foreground">
              <span>完成率 {{ pct(ws.completion_rate) }}</span>
              <span>价值 {{ fmt(ws.total_value) }}</span>
              <span>Token {{ fmt(ws.total_tokens, 0) }}</span>
              <span>ROI {{ fmt(ws.roi_per_1k_tokens) }}/k</span>
            </div>
          </div>

          <div v-if="ws.objectives.length > 0" class="space-y-2">
            <div
              v-for="obj in ws.objectives"
              :key="obj.id"
              class="flex items-center gap-3 px-3 py-2 rounded-lg bg-muted/50"
            >
              <span class="text-[10px] px-1.5 py-0.5 rounded bg-primary/20 text-primary font-medium shrink-0">O</span>
              <span class="text-sm flex-1">{{ obj.title }}</span>
              <span class="text-xs text-muted-foreground shrink-0">{{ obj.kr_count }} KR</span>
              <div class="w-24 h-1.5 bg-muted rounded-full overflow-hidden shrink-0">
                <div
                  class="h-full rounded-full transition-all"
                  :class="obj.progress >= 1 ? 'bg-green-500' : 'bg-primary'"
                  :style="{ width: `${Math.min(100, Math.round(obj.progress * 100))}%` }"
                />
              </div>
              <span class="text-xs text-muted-foreground w-10 text-right shrink-0">{{ Math.round(obj.progress * 100) }}%</span>
            </div>
          </div>

          <div v-else class="text-xs text-muted-foreground">暂无目标</div>
        </div>
      </div>
    </template>

    <div v-else class="text-center text-muted-foreground py-16">
      暂无数据
    </div>
  </div>
</template>
