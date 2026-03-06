<script setup lang="ts">
import { ref, onBeforeUnmount } from 'vue'
import { FileText, Image as ImageIcon, Download, X, Loader2 } from 'lucide-vue-next'
import { useWorkspaceStore, type FileAttachment } from '@/stores/workspace'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  attachments: FileAttachment[]
  workspaceId: string
}>()

const { t } = useI18n()
const store = useWorkspaceStore()
const loadingUrls = ref<Set<string>>(new Set())

const lightboxUrl = ref<string | null>(null)
const lightboxAtt = ref<FileAttachment | null>(null)
const lightboxLoading = ref(false)

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`
}

function isImage(att: FileAttachment): boolean {
  return att.content_type?.startsWith('image/') ?? false
}

async function handleClick(att: FileAttachment) {
  if (isImage(att)) {
    await openPreview(att)
  } else {
    await download(att)
  }
}

async function openPreview(att: FileAttachment) {
  lightboxAtt.value = att
  lightboxLoading.value = true
  lightboxUrl.value = null
  try {
    const url = await store.getFileUrl(props.workspaceId, att.id)
    if (url) {
      lightboxUrl.value = url
    } else {
      lightboxAtt.value = null
    }
  } catch {
    lightboxAtt.value = null
  } finally {
    lightboxLoading.value = false
  }
}

function closeLightbox() {
  lightboxUrl.value = null
  lightboxAtt.value = null
  lightboxLoading.value = false
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && lightboxAtt.value) closeLightbox()
}

document.addEventListener('keydown', onKeydown)
onBeforeUnmount(() => document.removeEventListener('keydown', onKeydown))

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
      :title="isImage(att) ? t('chat.previewImage') : t('chat.downloadFile')"
      @click="handleClick(att)"
    >
      <ImageIcon v-if="isImage(att)" class="w-3.5 h-3.5 shrink-0 text-muted-foreground" />
      <FileText v-else class="w-3.5 h-3.5 shrink-0 text-muted-foreground" />
      <span class="truncate max-w-[120px]">{{ att.name }}</span>
      <span class="text-muted-foreground shrink-0">({{ formatFileSize(att.size) }})</span>
      <Download v-if="!isImage(att)" class="w-3 h-3 shrink-0 text-muted-foreground" />
    </button>
  </div>

  <Teleport to="body">
    <div
      v-if="lightboxAtt"
      class="lightbox-overlay"
      @click.self="closeLightbox"
    >
      <button
        class="lightbox-close"
        :title="t('chat.closePreview')"
        @click="closeLightbox"
      >
        <X class="w-5 h-5" />
      </button>

      <div v-if="lightboxLoading" class="lightbox-spinner">
        <Loader2 class="w-8 h-8 animate-spin text-white/70" />
      </div>

      <img
        v-else-if="lightboxUrl"
        :src="lightboxUrl"
        :alt="lightboxAtt.name"
        class="lightbox-image"
      />

      <div v-if="lightboxAtt && !lightboxLoading" class="lightbox-caption">
        {{ lightboxAtt.name }}
        <span class="opacity-60">({{ formatFileSize(lightboxAtt.size) }})</span>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.lightbox-overlay {
  position: fixed;
  inset: 0;
  z-index: 99999;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.85);
}

.lightbox-close {
  position: absolute;
  top: 16px;
  right: 16px;
  padding: 8px;
  border-radius: 8px;
  color: white;
  opacity: 0.7;
  transition: opacity 0.15s;
}
.lightbox-close:hover {
  opacity: 1;
}

.lightbox-spinner {
  display: flex;
  align-items: center;
  justify-content: center;
}

.lightbox-image {
  max-width: 90vw;
  max-height: 85vh;
  object-fit: contain;
  border-radius: 4px;
}

.lightbox-caption {
  position: absolute;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  color: white;
  font-size: 0.8rem;
  padding: 6px 16px;
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.5);
  white-space: nowrap;
}
</style>
