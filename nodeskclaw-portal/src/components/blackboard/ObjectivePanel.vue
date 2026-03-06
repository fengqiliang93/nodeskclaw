<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Target, Loader2, ChevronRight } from 'lucide-vue-next'
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
          <div class="flex items-center gap-1.5">
            <span class="text-[10px] px-1.5 py-0.5 rounded font-medium"
              :class="obj.obj_type === 'key_result' ? 'bg-blue-500/20 text-blue-400' : 'bg-primary/20 text-primary'"
            >{{ obj.obj_type === 'key_result' ? 'KR' : 'O' }}</span>
            <span class="text-sm font-medium">{{ obj.title }}</span>
          </div>
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

        <div v-if="obj.children && obj.children.length > 0" class="ml-4 space-y-1.5 pt-1 border-l border-border/50 pl-3">
          <div
            v-for="kr in obj.children"
            :key="kr.id"
            class="p-2 rounded bg-muted/30 space-y-1"
          >
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-1">
                <ChevronRight class="w-3 h-3 text-muted-foreground" />
                <span class="text-[10px] px-1 py-0.5 rounded bg-blue-500/20 text-blue-400 font-medium">KR</span>
                <span class="text-xs font-medium">{{ kr.title }}</span>
              </div>
              <span class="text-[10px] text-muted-foreground">{{ Math.round(kr.progress * 100) }}%</span>
            </div>
            <div class="w-full h-1 bg-muted rounded-full overflow-hidden">
              <div
                class="h-full rounded-full transition-all duration-300"
                :class="kr.progress >= 1 ? 'bg-green-500' : 'bg-blue-500'"
                :style="{ width: `${Math.min(100, Math.round(kr.progress * 100))}%` }"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
