<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSvgZoom } from '@/composables/useSvgZoom'
import { axialToWorld } from '@/composables/useHexLayout'
import type { TopologyNode, TopologyEdge } from '@/stores/workspace'

const props = defineProps<{
  nodes: TopologyNode[]
  edges: TopologyEdge[]
}>()

const { t } = useI18n()
const svgRef = ref<SVGSVGElement | null>(null)
const { transformStr } = useSvgZoom(svgRef, { minZoom: 0.3, maxZoom: 4 })

const hoveredKey = ref<string | null>(null)

const SCALE = 80
const PADDING = 60

const NODE_STYLES: Record<string, { color: string; radius: number }> = {
  blackboard: { color: 'hsl(var(--primary))', radius: 18 },
  agent: { color: '#3b82f6', radius: 14 },
  human: { color: '#f59e0b', radius: 14 },
  corridor: { color: 'hsl(var(--muted-foreground))', radius: 8 },
}

function nodeKey(q: number, r: number) {
  return `${q},${r}`
}

interface PositionedNode extends TopologyNode {
  px: number
  py: number
  key: string
}

const positionedNodes = computed<PositionedNode[]>(() =>
  props.nodes.map(n => {
    const w = axialToWorld(n.hex_q, n.hex_r)
    return { ...n, px: w.x * SCALE, py: w.y * SCALE, key: nodeKey(n.hex_q, n.hex_r) }
  }),
)

const nodeMap = computed(() => {
  const m = new Map<string, PositionedNode>()
  for (const n of positionedNodes.value) m.set(n.key, n)
  return m
})

interface PositionedEdge extends TopologyEdge {
  x1: number; y1: number; x2: number; y2: number
  keyA: string; keyB: string
}

const positionedEdges = computed<PositionedEdge[]>(() => {
  const m = nodeMap.value
  return props.edges
    .map(e => {
      const kA = nodeKey(e.a_q, e.a_r)
      const kB = nodeKey(e.b_q, e.b_r)
      const nA = m.get(kA)
      const nB = m.get(kB)
      if (!nA || !nB) return null
      return { ...e, x1: nA.px, y1: nA.py, x2: nB.px, y2: nB.py, keyA: kA, keyB: kB }
    })
    .filter((e): e is PositionedEdge => e !== null)
})

const viewBox = computed(() => {
  const ns = positionedNodes.value
  if (ns.length === 0) return '0 0 400 300'
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity
  for (const n of ns) {
    if (n.px < minX) minX = n.px
    if (n.px > maxX) maxX = n.px
    if (n.py < minY) minY = n.py
    if (n.py > maxY) maxY = n.py
  }
  const w = maxX - minX || 200
  const h = maxY - minY || 150
  return `${minX - PADDING} ${minY - PADDING} ${w + PADDING * 2} ${h + PADDING * 2}`
})

const connectedKeys = computed(() => {
  if (!hoveredKey.value) return null
  const keys = new Set<string>([hoveredKey.value])
  for (const e of positionedEdges.value) {
    if (e.keyA === hoveredKey.value) keys.add(e.keyB)
    else if (e.keyB === hoveredKey.value) keys.add(e.keyA)
  }
  return keys
})

function nodeOpacity(key: string): number {
  if (!connectedKeys.value) return 1
  return connectedKeys.value.has(key) ? 1 : 0.15
}

function edgeOpacity(e: PositionedEdge): number {
  if (!connectedKeys.value) return 1
  return (connectedKeys.value.has(e.keyA) && connectedKeys.value.has(e.keyB)) ? 1 : 0.08
}

function nodeLabel(n: TopologyNode): string {
  return n.display_name || n.entity_id || ''
}

function nodeStyle(type: string) {
  return NODE_STYLES[type] || NODE_STYLES.corridor
}

const legendItems = computed(() => [
  { type: 'blackboard', labelKey: 'blackboard.topoBlackboardNode' },
  { type: 'agent', labelKey: 'blackboard.topoAgentNode' },
  { type: 'human', labelKey: 'blackboard.topoHumanNode' },
  { type: 'corridor', labelKey: 'blackboard.topoCorridorNode' },
])
</script>

<template>
  <div class="relative w-full h-full min-h-[300px]">
    <svg
      ref="svgRef"
      class="w-full h-full"
      :viewBox="viewBox"
      @contextmenu.prevent
    >
      <g :transform="transformStr">
        <line
          v-for="(edge, i) in positionedEdges"
          :key="'e-' + i"
          :x1="edge.x1"
          :y1="edge.y1"
          :x2="edge.x2"
          :y2="edge.y2"
          :stroke="edge.auto_created ? 'hsl(var(--border))' : 'hsl(var(--muted-foreground))'"
          :stroke-width="edge.auto_created ? 1.5 : 2"
          :stroke-dasharray="edge.auto_created ? '6 4' : 'none'"
          :opacity="edgeOpacity(edge)"
          class="transition-opacity duration-200"
        />

        <g
          v-for="node in positionedNodes"
          :key="node.key"
          :transform="`translate(${node.px}, ${node.py})`"
          :opacity="nodeOpacity(node.key)"
          class="transition-opacity duration-200 cursor-pointer"
          @pointerenter="hoveredKey = node.key"
          @pointerleave="hoveredKey = null"
        >
          <circle
            :r="nodeStyle(node.node_type).radius"
            :fill="nodeStyle(node.node_type).color"
            fill-opacity="0.15"
            :stroke="nodeStyle(node.node_type).color"
            stroke-width="2"
          />
          <circle
            :r="nodeStyle(node.node_type).radius * 0.4"
            :fill="nodeStyle(node.node_type).color"
          />
          <text
            :y="nodeStyle(node.node_type).radius + 14"
            text-anchor="middle"
            fill="hsl(var(--foreground))"
            font-size="11"
            class="select-none pointer-events-none"
          >{{ nodeLabel(node) }}</text>
        </g>
      </g>
    </svg>

    <div class="absolute bottom-3 right-3 bg-card/90 backdrop-blur-sm border border-border rounded-lg px-3 py-2 text-xs space-y-1.5">
      <div
        v-for="item in legendItems"
        :key="item.type"
        class="flex items-center gap-2"
      >
        <span
          class="inline-block rounded-full"
          :style="{
            width: nodeStyle(item.type).radius + 'px',
            height: nodeStyle(item.type).radius + 'px',
            backgroundColor: nodeStyle(item.type).color,
            opacity: 0.8,
          }"
        />
        <span class="text-muted-foreground">{{ t(item.labelKey) }}</span>
      </div>
      <div class="border-t border-border pt-1.5 mt-1.5 space-y-1">
        <div class="flex items-center gap-2">
          <span class="inline-block w-5 border-t-2 border-[hsl(var(--muted-foreground))]" />
          <span class="text-muted-foreground">{{ t('blackboard.topoManual') }}</span>
        </div>
        <div class="flex items-center gap-2">
          <span class="inline-block w-5 border-t-2 border-dashed border-[hsl(var(--border))]" />
          <span class="text-muted-foreground">{{ t('blackboard.topoAutoCreated') }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
