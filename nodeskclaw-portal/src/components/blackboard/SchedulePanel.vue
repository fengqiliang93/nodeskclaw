<script setup lang="ts">
import { computed } from 'vue'
import { Timer } from 'lucide-vue-next'
import { useWorkspaceStore, type ScheduleInfo } from '@/stores/workspace'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  workspaceId: string
}>()

const { t } = useI18n()
const store = useWorkspaceStore()

const schedules = computed(() => store.schedules)

function cronToHuman(expr: string): string {
  const parts = expr.trim().split(/\s+/)
  if (parts.length < 5) return expr

  const [minute, hour, dom, , dow] = parts

  if (hour.startsWith('*/')) {
    const n = hour.slice(2)
    return t('blackboard.cronEveryNHours', { n })
  }

  if (dom === '*' && dow === '*' && /^\d+$/.test(hour) && /^\d+$/.test(minute)) {
    return t('blackboard.cronDailyAt', { time: `${hour.padStart(2, '0')}:${minute.padStart(2, '0')}` })
  }

  if (dom === '*' && /^\d+$/.test(dow) && /^\d+$/.test(hour) && /^\d+$/.test(minute)) {
    const days = [
      t('blackboard.cronSun'), t('blackboard.cronMon'), t('blackboard.cronTue'),
      t('blackboard.cronWed'), t('blackboard.cronThu'), t('blackboard.cronFri'), t('blackboard.cronSat'),
    ]
    const dayName = days[Number(dow)] || dow
    const time = `${hour.padStart(2, '0')}:${minute.padStart(2, '0')}`
    return t('blackboard.cronWeeklyAt', { day: dayName, time })
  }

  return expr
}

async function toggle(schedule: ScheduleInfo) {
  try {
    await store.toggleScheduleActive(props.workspaceId, schedule.id, !schedule.is_active)
  } catch (e) {
    console.error('toggleSchedule error:', e)
  }
}
</script>

<template>
  <div class="space-y-3">
    <h3 class="text-sm font-medium text-muted-foreground flex items-center gap-1.5">
      <Timer class="w-4 h-4" />
      {{ t('blackboard.schedules') }}
    </h3>

    <div v-if="schedules.length === 0" class="text-sm text-muted-foreground px-1">
      {{ t('blackboard.noSchedules') }}
    </div>

    <div v-else class="space-y-2">
      <div
        v-for="schedule in schedules"
        :key="schedule.id"
        class="flex items-center justify-between px-3 py-2.5 rounded-lg bg-muted/50"
      >
        <div class="flex-1 min-w-0 mr-3">
          <div class="flex items-center gap-2">
            <span class="text-sm font-medium truncate">{{ schedule.name }}</span>
            <span class="text-xs px-1.5 py-0.5 rounded bg-muted text-muted-foreground shrink-0">
              {{ cronToHuman(schedule.cron_expr) }}
            </span>
          </div>
          <p class="text-xs text-muted-foreground mt-0.5 line-clamp-1">{{ schedule.message_template }}</p>
        </div>

        <button
          role="switch"
          :aria-checked="schedule.is_active"
          class="relative inline-flex h-5 w-9 shrink-0 rounded-full transition-colors duration-200"
          :class="schedule.is_active ? 'bg-primary' : 'bg-muted-foreground/30'"
          @click="toggle(schedule)"
        >
          <span
            class="pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow transform transition-transform duration-200 mt-0.5"
            :class="schedule.is_active ? 'translate-x-[18px]' : 'translate-x-0.5'"
          />
        </button>
      </div>
    </div>
  </div>
</template>
