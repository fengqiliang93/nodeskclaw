<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { Archive, AlertCircle, Clock, CheckCircle2, Play, Plus, Loader2 } from 'lucide-vue-next'
import { useWorkspaceStore, type TaskInfo } from '@/stores/workspace'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  workspaceId: string
}>()

const { t } = useI18n()
const store = useWorkspaceStore()

const tasks = ref<TaskInfo[]>([])
const loading = ref(false)
const showArchived = ref(false)

const columns = computed(() => [
  { key: 'pending', label: t('blackboard.taskPending'), icon: Clock, color: 'text-yellow-500' },
  { key: 'in_progress', label: t('blackboard.taskInProgress'), icon: Play, color: 'text-blue-500' },
  { key: 'done', label: t('blackboard.taskDone'), icon: CheckCircle2, color: 'text-green-500' },
  { key: 'blocked', label: t('blackboard.taskBlocked'), icon: AlertCircle, color: 'text-red-500' },
])

function tasksByStatus(status: string) {
  return tasks.value.filter(t => t.status === status)
}

async function loadTasks() {
  loading.value = true
  try {
    tasks.value = await store.fetchTasks(props.workspaceId, undefined, !showArchived.value)
  } finally {
    loading.value = false
  }
}

async function onArchive(taskId: string) {
  await store.archiveTask(props.workspaceId, taskId)
  await loadTasks()
}

function priorityBadgeClass(priority: string) {
  const map: Record<string, string> = {
    urgent: 'bg-red-500/20 text-red-400',
    high: 'bg-orange-500/20 text-orange-400',
    medium: 'bg-blue-500/20 text-blue-400',
    low: 'bg-zinc-500/20 text-zinc-400',
  }
  return map[priority] || map.medium
}

onMounted(loadTasks)
watch(showArchived, loadTasks)

defineExpose({ refresh: loadTasks })
</script>

<template>
  <div class="space-y-3">
    <div class="flex items-center justify-between">
      <h3 class="text-sm font-medium text-muted-foreground">{{ t('blackboard.tasks') }}</h3>
      <label class="flex items-center gap-1.5 text-xs text-muted-foreground">
        <input type="checkbox" v-model="showArchived" class="rounded border-border" />
        {{ t('blackboard.showArchived') }}
      </label>
    </div>

    <div v-if="loading" class="flex justify-center py-8">
      <Loader2 class="w-5 h-5 animate-spin text-muted-foreground" />
    </div>

    <div v-else class="grid grid-cols-4 gap-3">
      <div v-for="col in columns" :key="col.key" class="space-y-2">
        <div class="flex items-center gap-1.5 mb-2">
          <component :is="col.icon" class="w-3.5 h-3.5" :class="col.color" />
          <span class="text-xs font-medium">{{ col.label }}</span>
          <span class="text-xs text-muted-foreground">({{ tasksByStatus(col.key).length }})</span>
        </div>

        <div
          v-for="task in tasksByStatus(col.key)"
          :key="task.id"
          class="p-2.5 rounded-lg bg-muted/50 border border-border/50 space-y-1.5 text-xs"
        >
          <div class="flex items-start justify-between gap-1">
            <span class="font-medium text-sm leading-tight">{{ task.title }}</span>
            <span v-if="task.priority" class="shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium" :class="priorityBadgeClass(task.priority)">
              {{ task.priority }}
            </span>
          </div>

          <p v-if="task.description" class="text-muted-foreground line-clamp-2">{{ task.description }}</p>

          <div v-if="task.assignee_name" class="text-muted-foreground">
            {{ t('blackboard.assignee') }}: {{ task.assignee_name }}
          </div>

          <div class="flex items-center gap-2 text-muted-foreground">
            <span v-if="task.estimated_value != null">{{ t('blackboard.estimatedValue') }}: {{ task.estimated_value }}</span>
            <span v-if="task.actual_value != null">{{ t('blackboard.actualValue') }}: {{ task.actual_value }}</span>
            <span v-if="task.token_cost != null">Token: {{ task.token_cost }}</span>
          </div>

          <div v-if="task.blocker_reason && task.status === 'blocked'" class="text-red-400 text-[11px]">
            {{ task.blocker_reason }}
          </div>

          <div v-if="task.status === 'done' && !task.archived_at" class="pt-1">
            <button
              class="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground transition-colors"
              @click="onArchive(task.id)"
            >
              <Archive class="w-3 h-3" />
              {{ t('blackboard.archive') }}
            </button>
          </div>
        </div>

        <div v-if="tasksByStatus(col.key).length === 0" class="text-center text-muted-foreground text-xs py-4">
          {{ t('blackboard.noTasks') }}
        </div>
      </div>
    </div>
  </div>
</template>
