<script setup lang="ts">
withDefaults(defineProps<{
  text?: string
  position?: 'top' | 'bottom'
}>(), {
  text: '',
  position: 'top',
})
</script>

<template>
  <span class="base-tooltip-wrap">
    <slot />
    <span
      v-if="text"
      class="base-tooltip-bubble"
      :class="position === 'bottom' ? 'base-tooltip-bottom' : 'base-tooltip-top'"
    >{{ text }}</span>
  </span>
</template>

<style scoped>
.base-tooltip-wrap {
  position: relative;
  display: inline-flex;
}

.base-tooltip-bubble {
  display: none;
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
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

.base-tooltip-top {
  bottom: calc(100% + 8px);
}

.base-tooltip-bottom {
  top: calc(100% + 8px);
}

.base-tooltip-wrap:hover .base-tooltip-bubble {
  display: block;
}
</style>
