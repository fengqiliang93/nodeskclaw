<script setup lang="ts">
import { ref } from 'vue'
import { FileText, Image as ImageIcon, Download } from 'lucide-vue-next'
import { useWorkspaceStore, type FileAttachment } from '@/stores/workspace'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  attachments: FileAttachment[]
  workspaceId: string
}>()

const { t } = useI18n()
const store = useWorkspaceStore()
const loadingUrls = ref<Set<string>>(new Set())

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`
}

function isImage(att: FileAttachment): boolean {
  return att.content_type?.startsWith('image/') ?? false
}

async function download(att: FileAttachment) {
  loadingUrls.value.add(att.id)
  try {
    const url = await store.getFileUrl(props.workspaceId, att.id)
    if (url) window.open(url, '_blank')
  } finally {
    loadingUrls.value.delete(att.id)
  }
}
</script>

<template>
  <div v-if="attachments?.length" class="flex flex-wrap gap-1.5 mt-1.5">
    <button
      v-for="att in attachments"
      :key="att.id"
      class="flex items-center gap-1.5 px-2 py-1 rounded-md border text-xs transition-colors bg-background/60 border-border/60 hover:bg-background hover:border-border"
      :title="t('chat.downloadFile')"
      @click="download(att)"
    >
      <ImageIcon v-if="isImage(att)" class="w-3.5 h-3.5 shrink-0 text-muted-foreground" />
      <FileText v-else class="w-3.5 h-3.5 shrink-0 text-muted-foreground" />
      <span class="truncate max-w-[120px]">{{ att.original_name }}</span>
      <span class="text-muted-foreground shrink-0">({{ formatFileSize(att.file_size) }})</span>
      <Download class="w-3 h-3 shrink-0 text-muted-foreground" />
    </button>
  </div>
</template>
