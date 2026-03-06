<script setup lang="ts">
import { ref, onBeforeUnmount } from 'vue'

const props = withDefaults(defineProps<{
  text?: string
  position?: 'top' | 'bottom'
}>(), {
  text: '',
  position: 'top',
})

const triggerRef = ref<HTMLElement | null>(null)
const visible = ref(false)
const tooltipStyle = ref<Record<string, string>>({})

let raf = 0

function show() {
  if (!props.text) return
  visible.value = true
  updatePosition()
}

function hide() {
  visible.value = false
  if (raf) cancelAnimationFrame(raf)
}

function updatePosition() {
  raf = requestAnimationFrame(() => {
    const el = triggerRef.value
    if (!el || !visible.value) return
    const rect = el.getBoundingClientRect()
    const left = rect.left + rect.width / 2
    if (props.position === 'bottom') {
      tooltipStyle.value = {
        top: `${rect.bottom + 8}px`,
        left: `${left}px`,
        transform: 'translateX(-50%)',
      }
    } else {
      tooltipStyle.value = {
        top: `${rect.top - 8}px`,
        left: `${left}px`,
        transform: 'translate(-50%, -100%)',
      }
    }
  })
}

onBeforeUnmount(() => { if (raf) cancelAnimationFrame(raf) })
</script>

<template>
  <span ref="triggerRef" class="inline-flex" @mouseenter="show" @mouseleave="hide">
    <slot />
  </span>
  <Teleport to="body">
    <span
      v-if="visible && text"
      class="base-tooltip-bubble"
      :style="tooltipStyle"
    >{{ text }}</span>
  </Teleport>
</template>

<style scoped>
.base-tooltip-bubble {
  position: fixed;
  white-space: nowrap;
  padding: 5px 12px;
  border-radius: 6px;
  font-size: 0.75rem;
  line-height: 1.4;
  color: var(--popover-foreground);
  background: var(--popover);
  border: 1px solid var(--border);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
  pointer-events: none;
  z-index: 99999;
}
</style>
