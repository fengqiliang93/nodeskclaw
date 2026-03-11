<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useOrgStore } from '@/stores/org'
import { useToast } from '@/composables/useToast'
import { resolveApiErrorMessage } from '@/i18n/error'
import { Pencil, Check, X, Loader2 } from 'lucide-vue-next'

const { t } = useI18n()
const orgStore = useOrgStore()
const toast = useToast()

const loading = ref(true)
const editing = ref(false)
const saving = ref(false)
const editName = ref('')

function startEdit() {
  editName.value = orgStore.currentOrg?.name ?? ''
  editing.value = true
}

function cancelEdit() {
  editing.value = false
}

async function saveName() {
  const trimmed = editName.value.trim()
  if (!trimmed || trimmed === orgStore.currentOrg?.name) {
    editing.value = false
    return
  }
  saving.value = true
  try {
    await orgStore.updateOrgName(trimmed)
    toast.success(t('orgSettings.nameUpdated'))
    editing.value = false
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t))
  } finally {
    saving.value = false
  }
}

function formatDate(iso: string | undefined): string {
  if (!iso) return '-'
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric', month: 'long', day: 'numeric',
  })
}

onMounted(async () => {
  await orgStore.fetchCurrentOrg()
  loading.value = false
})
</script>

<template>
  <div v-if="loading" class="flex items-center justify-center py-20">
    <Loader2 class="w-5 h-5 animate-spin text-muted-foreground" />
  </div>

  <div v-else-if="orgStore.currentOrg" class="space-y-6">
    <!-- 基本信息 -->
    <section class="rounded-xl border border-border bg-card p-5">
      <h2 class="text-sm font-semibold text-muted-foreground mb-4">{{ t('orgSettings.basicInfo') }}</h2>
      <div class="grid grid-cols-[140px_1fr] gap-y-4 items-center text-sm">
        <span class="text-muted-foreground">{{ t('orgSettings.orgName') }}</span>
        <div class="flex items-center gap-2">
          <template v-if="!editing">
            <span class="font-medium">{{ orgStore.currentOrg.name }}</span>
            <button
              class="p-1 rounded hover:bg-muted/60 text-muted-foreground hover:text-foreground transition-colors"
              :title="t('orgSettings.editName')"
              @click="startEdit"
            >
              <Pencil class="w-3.5 h-3.5" />
            </button>
          </template>
          <template v-else>
            <input
              v-model="editName"
              type="text"
              class="h-8 px-2 rounded-md border border-border bg-background text-sm w-60 focus:outline-none focus:ring-1 focus:ring-primary"
              @keyup.enter="saveName"
              @keyup.escape="cancelEdit"
            />
            <button
              class="p-1 rounded hover:bg-primary/10 text-primary transition-colors"
              :disabled="saving"
              @click="saveName"
            >
              <Loader2 v-if="saving" class="w-4 h-4 animate-spin" />
              <Check v-else class="w-4 h-4" />
            </button>
            <button
              class="p-1 rounded hover:bg-muted/60 text-muted-foreground transition-colors"
              :disabled="saving"
              @click="cancelEdit"
            >
              <X class="w-4 h-4" />
            </button>
          </template>
        </div>

        <span class="text-muted-foreground">{{ t('orgSettings.orgSlug') }}</span>
        <span class="font-mono text-xs bg-muted/50 px-2 py-1 rounded w-fit">{{ orgStore.currentOrg.slug }}</span>

        <span class="text-muted-foreground">{{ t('orgSettings.createdAt') }}</span>
        <span>{{ formatDate(orgStore.currentOrg.created_at) }}</span>
      </div>
    </section>

    <!-- 配额信息 -->
    <section class="rounded-xl border border-border bg-card p-5">
      <h2 class="text-sm font-semibold text-muted-foreground mb-4">{{ t('orgSettings.quotaInfo') }}</h2>
      <div class="grid grid-cols-[140px_1fr] gap-y-4 items-center text-sm">
        <span class="text-muted-foreground">{{ t('orgSettings.plan') }}</span>
        <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-primary/10 text-primary w-fit">
          {{ orgStore.currentOrg.plan }}
        </span>

        <span class="text-muted-foreground">{{ t('orgSettings.maxInstances') }}</span>
        <span>{{ orgStore.currentOrg.max_instances }}</span>

        <span class="text-muted-foreground">{{ t('orgSettings.maxCpu') }}</span>
        <span>{{ orgStore.currentOrg.max_cpu_total }}</span>

        <span class="text-muted-foreground">{{ t('orgSettings.maxMem') }}</span>
        <span>{{ orgStore.currentOrg.max_mem_total }}</span>

        <span class="text-muted-foreground">{{ t('orgSettings.maxStorage') }}</span>
        <span>{{ orgStore.currentOrg.max_storage_total }}</span>
      </div>
    </section>

    <!-- 关联信息 -->
    <section class="rounded-xl border border-border bg-card p-5">
      <h2 class="text-sm font-semibold text-muted-foreground mb-4">{{ t('orgSettings.relatedInfo') }}</h2>
      <div class="grid grid-cols-[140px_1fr] gap-y-4 items-center text-sm">
        <span class="text-muted-foreground">{{ t('orgSettings.clusterName') }}</span>
        <span v-if="orgStore.currentOrg.cluster_name">{{ orgStore.currentOrg.cluster_name }}</span>
        <span v-else class="text-muted-foreground/60 italic">{{ t('orgSettings.clusterNone') }}</span>

        <span class="text-muted-foreground">{{ t('orgSettings.memberCount') }}</span>
        <span>{{ orgStore.currentOrg.member_count }}</span>

        <span class="text-muted-foreground">{{ t('orgSettings.isActive') }}</span>
        <span
          class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium w-fit"
          :class="orgStore.currentOrg.is_active ? 'bg-green-500/15 text-green-400' : 'bg-red-500/15 text-red-400'"
        >
          {{ orgStore.currentOrg.is_active ? t('orgSettings.active') : t('orgSettings.inactive') }}
        </span>
      </div>
    </section>
  </div>
</template>
