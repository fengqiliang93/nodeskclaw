<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Loader2, Coins, ArrowUpRight, ArrowDownLeft } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'

const props = defineProps<{
  workspaceId: string
}>()

const { t } = useI18n()

const loading = ref(false)
const data = ref<{
  total_prompt_tokens: number
  total_completion_tokens: number
  total_tokens: number
  by_provider: { provider: string; model: string | null; prompt_tokens: number; completion_tokens: number; total_tokens: number; request_count: number }[]
} | null>(null)

async function loadUsage() {
  loading.value = true
  try {
    const res = await api.get(`/workspaces/${props.workspaceId}/token-usage`)
    data.value = res.data.data
  } catch {
    data.value = null
  } finally {
    loading.value = false
  }
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return n.toString()
}

onMounted(loadUsage)

defineExpose({ refresh: loadUsage })
</script>

<template>
  <div class="space-y-3">
    <h3 class="text-sm font-medium text-muted-foreground flex items-center gap-1.5">
      <Coins class="w-4 h-4" />
      {{ t('blackboard.tokenUsage') }}
    </h3>

    <div v-if="loading" class="flex justify-center py-4">
      <Loader2 class="w-4 h-4 animate-spin text-muted-foreground" />
    </div>

    <div v-else-if="!data || data.total_tokens === 0" class="text-xs text-muted-foreground text-center py-4">
      {{ t('blackboard.noTokenUsage') }}
    </div>

    <template v-else>
      <div class="grid grid-cols-3 gap-3">
        <div class="p-3 rounded-lg bg-muted/50 border border-border/50 space-y-1">
          <div class="text-[11px] text-muted-foreground flex items-center gap-1">
            <ArrowUpRight class="w-3 h-3" />
            {{ t('blackboard.promptTokens') }}
          </div>
          <div class="text-base font-semibold">{{ formatTokens(data.total_prompt_tokens) }}</div>
        </div>
        <div class="p-3 rounded-lg bg-muted/50 border border-border/50 space-y-1">
          <div class="text-[11px] text-muted-foreground flex items-center gap-1">
            <ArrowDownLeft class="w-3 h-3" />
            {{ t('blackboard.completionTokens') }}
          </div>
          <div class="text-base font-semibold">{{ formatTokens(data.total_completion_tokens) }}</div>
        </div>
        <div class="p-3 rounded-lg bg-muted/50 border border-border/50 space-y-1">
          <div class="text-[11px] text-muted-foreground">{{ t('blackboard.totalTokens') }}</div>
          <div class="text-base font-semibold">{{ formatTokens(data.total_tokens) }}</div>
        </div>
      </div>

      <div v-if="data.by_provider.length > 0" class="space-y-1">
        <div class="text-[11px] text-muted-foreground font-medium">{{ t('blackboard.tokensByProvider') }}</div>
        <div class="space-y-1">
          <div
            v-for="(item, i) in data.by_provider"
            :key="i"
            class="flex items-center justify-between text-xs px-2 py-1.5 rounded bg-muted/30"
          >
            <div class="flex items-center gap-1.5">
              <span class="font-medium">{{ item.provider }}</span>
              <span v-if="item.model" class="text-muted-foreground">{{ item.model }}</span>
            </div>
            <div class="flex items-center gap-3 text-muted-foreground">
              <span>{{ formatTokens(item.prompt_tokens) }} / {{ formatTokens(item.completion_tokens) }}</span>
              <span class="font-medium text-foreground">{{ formatTokens(item.total_tokens) }}</span>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
