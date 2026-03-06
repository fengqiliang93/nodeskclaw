<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Target, Loader2 } from 'lucide-vue-next'
import { useWorkspaceStore, type ObjectiveInfo } from '@/stores/workspace'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  workspaceId: string
}>()

const { t } = useI18n()
const store = useWorkspaceStore()

const objectives = ref<ObjectiveInfo[]>([])
const loading = ref(false)

async function loadObjectives() {
  loading.value = true
  try {
    objectives.value = await store.fetchObjectives(props.workspaceId)
  } finally {
    loading.value = false
  }
}

onMounted(loadObjectives)

defineExpose({ refresh: loadObjectives })
</script>

<template>
  <div class="space-y-3">
    <h3 class="text-sm font-medium text-muted-foreground flex items-center gap-1.5">
      <Target class="w-3.5 h-3.5" />
      {{ t('blackboard.objectives') }}
    </h3>

    <div v-if="loading" class="flex justify-center py-4">
      <Loader2 class="w-4 h-4 animate-spin text-muted-foreground" />
    </div>

    <div v-else-if="objectives.length === 0" class="text-muted-foreground text-xs py-2">
      {{ t('blackboard.noObjectives') }}
    </div>

    <div v-else class="space-y-2">
      <div
        v-for="obj in objectives"
        :key="obj.id"
        class="p-3 rounded-lg bg-muted/50 border border-border/50 space-y-2"
      >
        <div class="flex items-center justify-between">
          <span class="text-sm font-medium">{{ obj.title }}</span>
          <span class="text-xs text-muted-foreground">{{ Math.round(obj.progress * 100) }}%</span>
        </div>

        <div class="w-full h-1.5 bg-muted rounded-full overflow-hidden">
          <div
            class="h-full rounded-full transition-all duration-300"
            :class="obj.progress >= 1 ? 'bg-green-500' : 'bg-primary'"
            :style="{ width: `${Math.min(100, Math.round(obj.progress * 100))}%` }"
          />
        </div>

        <p v-if="obj.description" class="text-xs text-muted-foreground line-clamp-2">{{ obj.description }}</p>
      </div>
    </div>
  </div>
</template>
