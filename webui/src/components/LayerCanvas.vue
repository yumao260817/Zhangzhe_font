<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps({
  layers: { type: Array, default: () => [] },
  selectedId: { type: String, default: null },
  referenceUrl: { type: String, default: null },
  referenceOpacity: { type: Number, default: 0.25 },
})

const emit = defineEmits(['select', 'update', 'delete'])

const box = ref(null)
const canvasSize = 512 // 与后端 GRID 一致

function localPoint(e) {
  const rect = box.value.getBoundingClientRect()
  return {
    x: ((e.clientX - rect.left) / rect.width) * canvasSize,
    y: ((e.clientY - rect.top) / rect.height) * canvasSize,
  }
}

const drag = ref(null)

function onPointerDown(e, layer) {
  e.preventDefault()
  e.stopPropagation()
  emit('select', layer.id)
  const p = localPoint(e)
  drag.value = { id: layer.id, dx: p.x - layer.x, dy: p.y - layer.y }
  box.value.setPointerCapture(e.pointerId)
}

function onPointerMove(e) {
  if (!drag.value) return
  const p = localPoint(e)
  const layer = props.layers.find((l) => l.id === drag.value.id)
  if (!layer) return
  emit('update', { ...layer, x: Math.round(p.x - drag.value.dx), y: Math.round(p.y - drag.value.dy) })
}

function onPointerUp() {
  drag.value = null
}

function onWheel(e) {
  if (!props.selectedId) return
  e.preventDefault()
  const layer = props.layers.find((l) => l.id === props.selectedId)
  if (!layer) return
  const factor = e.deltaY < 0 ? 1.08 : 0.925
  emit('update', {
    ...layer,
    scale_w: Math.max(8, Math.round(layer.scale_w * factor)),
    scale_h: Math.max(8, Math.round(layer.scale_h * factor)),
  })
}

onMounted(() => {
  if (box.value) box.value.addEventListener('wheel', onWheel, { passive: false })
})
onBeforeUnmount(() => {
  if (box.value) box.value.removeEventListener('wheel', onWheel)
})
</script>

<template>
  <div
    ref="box"
    class="canvas"
    @pointermove="onPointerMove"
    @pointerup="onPointerUp"
    @pointercancel="onPointerUp"
    @pointerdown="(e) => { if (e.target === box) emit('select', null) }"
  >
    <img
      v-if="referenceUrl"
      :src="referenceUrl"
      class="ref"
      :style="{ opacity: referenceOpacity }"
      alt="参考字形"
    />
    <div
      v-for="layer in layers"
      :key="layer.id"
      class="layer"
      :class="{ active: layer.id === selectedId }"
      :style="{
        left: layer.x + 'px',
        top: layer.y + 'px',
        width: layer.scale_w + 'px',
        height: layer.scale_h + 'px',
        transform: `rotate(${layer.angle || 0}deg) ${layer.flip ? 'scaleX(-1)' : ''}`,
        filter: layer.id === selectedId ? 'drop-shadow(0 0 4px rgba(30,120,255,.9))' : '',
      }"
      @pointerdown="(e) => onPointerDown(e, layer)"
    >
      <img :src="layer.url" draggable="false" alt="部件" />
    </div>
  </div>
</template>

<style scoped>
.canvas {
  position: relative;
  width: 512px;
  height: 512px;
  background:
    linear-gradient(45deg, #f2f2f2 25%, transparent 25%, transparent 75%, #f2f2f2 75%),
    linear-gradient(45deg, #f2f2f2 25%, #fff 25%, #fff 75%, #f2f2f2 75%);
  background-size: 16px 16px;
  background-position: 0 0, 8px 8px;
  border: 1px solid #ccc;
  border-radius: 6px;
  overflow: hidden;
  user-select: none;
  touch-action: none;
  cursor: grab;
}
.ref {
  position: absolute;
  left: 0;
  top: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
.layer {
  position: absolute;
  cursor: move;
  transform-origin: center;
}
.layer img {
  width: 100%;
  height: 100%;
  pointer-events: none;
  display: block;
}
</style>
