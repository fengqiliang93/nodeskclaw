<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { X, Save, RotateCcw, Paintbrush } from 'lucide-vue-next'
import { FLOOR_ASSETS, FURNITURE_ASSETS, type DecorationAsset } from '@/config/decorationAssets'
import type { HexDecoration } from '@/stores/workspace'

const props = defineProps<{
  selectedHexKey: string | null
  hexDecoration: HexDecoration | null
  saving?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:hex-decoration', deco: HexDecoration): void
  (e: 'save'): void
  (e: 'close'): void
}>()

const { t } = useI18n()

const selectedFloor = ref<string | null>(null)

watch(() => props.hexDecoration, (deco) => {
  selectedFloor.value = deco?.floor_asset_id ?? null
}, { immediate: true })

const furnitureList = computed(() => props.hexDecoration?.furniture ?? [])

function selectFloor(asset: DecorationAsset | null) {
  selectedFloor.value = asset?.id ?? null
  emit('update:hex-decoration', {
    floor_asset_id: asset?.id ?? null,
    furniture: furnitureList.value,
  })
}

function toggleFurniture(assetId: string) {
  const current = [...furnitureList.value]
  const idx = current.indexOf(assetId)
  if (idx >= 0) {
    current.splice(idx, 1)
  } else {
    current.push(assetId)
  }
  emit('update:hex-decoration', {
    floor_asset_id: selectedFloor.value,
    furniture: current,
  })
}

function resetDecoration() {
  selectedFloor.value = null
  emit('update:hex-decoration', { floor_asset_id: null, furniture: [] })
}

function hasFurniture(assetId: string): boolean {
  return furnitureList.value.includes(assetId)
}
</script>

<template>
  <div class="flex flex-col h-full bg-gray-900/95 text-gray-200 w-64 border-l border-gray-700/50">
    <div class="flex items-center justify-between px-3 py-2 border-b border-gray-700/50">
      <div class="flex items-center gap-2">
        <Paintbrush class="w-4 h-4 text-purple-400" />
        <span class="font-medium text-sm">{{ t('decoration.panel_title') }}</span>
      </div>
      <button class="p-1 rounded hover:bg-gray-700/50" @click="emit('close')">
        <X class="w-4 h-4" />
      </button>
    </div>

    <template v-if="selectedHexKey">
      <div class="px-3 py-2 border-b border-gray-700/50 text-xs text-gray-400">
        {{ t('decoration.current_hex', { name: selectedHexKey }) }}
      </div>

      <div class="flex-1 overflow-y-auto px-3 py-3 space-y-4">
        <section>
          <h3 class="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2">
            {{ t('decoration.floor.title') }}
          </h3>
          <div class="grid grid-cols-3 gap-2">
            <button
              class="aspect-square rounded border-2 overflow-hidden transition-all"
              :class="selectedFloor === null ? 'border-purple-500 ring-1 ring-purple-500/50' : 'border-gray-700 hover:border-gray-500'"
              @click="selectFloor(null)"
            >
              <div class="w-full h-full bg-gray-800 flex items-center justify-center">
                <X class="w-4 h-4 text-gray-500" />
              </div>
            </button>
            <button
              v-for="asset in FLOOR_ASSETS"
              :key="asset.id"
              class="aspect-square rounded border-2 overflow-hidden transition-all"
              :class="selectedFloor === asset.id ? 'border-purple-500 ring-1 ring-purple-500/50' : 'border-gray-700 hover:border-gray-500'"
              @click="selectFloor(asset)"
            >
              <img :src="asset.url" :alt="t(asset.nameKey)" class="w-full h-full object-cover" />
            </button>
          </div>
        </section>

        <section>
          <h3 class="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2">
            {{ t('decoration.furniture.title') }}
          </h3>
          <p class="text-xs text-gray-500 mb-2">{{ t('decoration.furniture.hint') }}</p>
          <div class="grid grid-cols-3 gap-2">
            <button
              v-for="asset in FURNITURE_ASSETS"
              :key="asset.id"
              class="aspect-square rounded border-2 overflow-hidden transition-all relative"
              :class="hasFurniture(asset.id) ? 'border-green-500 ring-1 ring-green-500/50' : 'border-gray-700 hover:border-gray-500'"
              @click="toggleFurniture(asset.id)"
            >
              <img :src="asset.url" :alt="t(asset.nameKey)" class="w-full h-full object-contain p-1" />
            </button>
          </div>
        </section>
      </div>

      <div class="flex items-center gap-2 px-3 py-2 border-t border-gray-700/50">
        <button
          class="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs rounded bg-purple-600 hover:bg-purple-500 transition-colors"
          :disabled="saving"
          @click="emit('save')"
        >
          <Save class="w-3.5 h-3.5" />
          {{ saving ? t('common.saving') : t('common.save') }}
        </button>
        <button
          class="flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs rounded bg-gray-700 hover:bg-gray-600 transition-colors"
          @click="resetDecoration"
        >
          <RotateCcw class="w-3.5 h-3.5" />
          {{ t('decoration.reset') }}
        </button>
      </div>
    </template>

    <template v-else>
      <div class="flex-1 flex items-center justify-center px-4">
        <p class="text-sm text-gray-500 text-center">{{ t('decoration.select_hex_hint') }}</p>
      </div>
    </template>
  </div>
</template>
