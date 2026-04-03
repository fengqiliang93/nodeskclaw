<script setup lang="ts">
import { ref, inject, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { Archive, RotateCcw, Trash2, Loader2, Plus, RefreshCw } from 'lucide-vue-next'
import api from '@/services/api'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'

const { t } = useI18n()
const router = useRouter()
const toast = useToast()
const { confirm } = useConfirm()

const instanceId = inject<any>('instanceId')

interface Backup {
  id: string
  instance_id: string
  type: string
  status: string
  data_size: number | null
  message: string | null
  created_at: string
  completed_at: string | null
}

const backups = ref<Backup[]>([])
const loading = ref(false)
const creating = ref(false)

async function fetchBackups() {
  loading.value = true
  try {
    const { data } = await api.get(`/instances/${instanceId.value}/backups`)
    backups.value = data.data ?? []
  } catch {
    backups.value = []
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  creating.value = true
  try {
    await api.post(`/instances/${instanceId.value}/backups`)
    toast.success(t('backup.backupSuccess'))
    await fetchBackups()
  } catch (e: any) {
    toast.error(e?.response?.data?.message || t('common.failed'))
  } finally {
    creating.value = false
  }
}

async function handleRestore(backupId: string) {
  const ok = await confirm({
    title: t('backup.restore'),
    description: t('backup.confirmRestore'),
    variant: 'danger',
  })
  if (!ok) return
  try {
    const { data } = await api.post(`/instances/${instanceId.value}/restore`, { backup_id: backupId })
    toast.success(t('backup.restoreSuccess'))
    if (data.data?.deploy_id) {
      router.push({ name: 'DeployProgress', params: { deployId: data.data.deploy_id } })
    }
  } catch (e: any) {
    toast.error(e?.response?.data?.message || t('common.failed'))
  }
}

async function handleDelete(backupId: string) {
  const ok = await confirm({
    title: t('backup.delete'),
    description: t('common.confirm') + '?',
    variant: 'danger',
  })
  if (!ok) return
  try {
    await api.delete(`/instances/${instanceId.value}/backups/${backupId}`)
    toast.success(t('backup.deleteSuccess'))
    await fetchBackups()
  } catch (e: any) {
    toast.error(e?.response?.data?.message || t('common.failed'))
  }
}

function formatSize(bytes: number | null): string {
  if (!bytes) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1048576).toFixed(1)} MB`
}

function formatTime(iso: string | null): string {
  if (!iso) return '-'
  return new Date(iso).toLocaleString()
}

function statusLabel(status: string): string {
  const key = `backup.status_${status}`
  return t(key)
}

onMounted(fetchBackups)
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h2 class="text-lg font-semibold">{{ t('backup.title') }}</h2>
      <div class="flex gap-2">
        <button
          class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border text-sm hover:bg-card transition-colors"
          @click="fetchBackups"
        >
          <RefreshCw class="w-4 h-4" />
        </button>
        <button
          class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-sm hover:bg-primary/90 transition-colors disabled:opacity-50"
          :disabled="creating"
          @click="handleCreate"
        >
          <Loader2 v-if="creating" class="w-4 h-4 animate-spin" />
          <Plus v-else class="w-4 h-4" />
          {{ t('backup.create') }}
        </button>
      </div>
    </div>

    <div v-if="loading" class="flex items-center justify-center py-12">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <div v-else-if="backups.length === 0" class="flex flex-col items-center justify-center py-12 text-muted-foreground">
      <Archive class="w-10 h-10 mb-3 opacity-40" />
      <p>{{ t('backup.empty') }}</p>
    </div>

    <div v-else class="border border-border rounded-lg overflow-hidden">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-border bg-muted/30">
            <th class="text-left px-4 py-2.5 font-medium">{{ t('backup.createdAt') }}</th>
            <th class="text-left px-4 py-2.5 font-medium">{{ t('backup.size') }}</th>
            <th class="text-left px-4 py-2.5 font-medium">{{ t('status.pending') }}</th>
            <th class="text-right px-4 py-2.5 font-medium"></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="b in backups" :key="b.id"
            class="border-b border-border last:border-0 hover:bg-muted/20"
          >
            <td class="px-4 py-2.5">{{ formatTime(b.created_at) }}</td>
            <td class="px-4 py-2.5">{{ formatSize(b.data_size) }}</td>
            <td class="px-4 py-2.5">
              <span
                :class="{
                  'text-green-400': b.status === 'completed',
                  'text-yellow-400': b.status === 'in_progress' || b.status === 'pending',
                  'text-red-400': b.status === 'failed',
                }"
              >{{ statusLabel(b.status) }}</span>
              <span v-if="b.message" class="ml-2 text-muted-foreground text-xs">{{ b.message }}</span>
            </td>
            <td class="px-4 py-2.5 text-right">
              <div class="flex items-center justify-end gap-2">
                <button
                  v-if="b.status === 'completed'"
                  class="flex items-center gap-1 px-2.5 py-1 rounded border border-border text-xs hover:bg-card transition-colors"
                  @click="handleRestore(b.id)"
                >
                  <RotateCcw class="w-3.5 h-3.5" />
                  {{ t('backup.restore') }}
                </button>
                <button
                  class="flex items-center gap-1 px-2.5 py-1 rounded border border-red-500/30 text-red-400 text-xs hover:bg-red-500/10 transition-colors"
                  @click="handleDelete(b.id)"
                >
                  <Trash2 class="w-3.5 h-3.5" />
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
