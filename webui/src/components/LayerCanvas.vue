<script setup>
import { ref } from 'vue'

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

const resize = ref(null)

function onResizeStart(e, layer, sx, sy) {
  e.preventDefault()
  e.stopPropagation()
  emit('select', layer.id)
  const p = localPoint(e)
  resize.value = {
    id: layer.id,
    startW: layer.scale_w,
    startH: layer.scale_h,
    startX: layer.x,
    startY: layer.y,
    sx: p.x,
    sy: p.y,
    dx: sx,
    dy: sy,
  }
  box.value.setPointerCapture(e.pointerId)
}

function onPointerMove(e) {
  if (drag.value) {
    const p = localPoint(e)
    const layer = props.layers.find((l) => l.id === drag.value.id)
    if (!layer) return
    emit('update', { ...layer, x: Math.round(p.x - drag.value.dx), y: Math.round(p.y - drag.value.dy) })
  } else if (resize.value) {
    const p = localPoint(e)
    const layer = props.layers.find((l) => l.id === resize.value.id)
    if (!layer) return
    const r = resize.value
    const d = Math.max((p.x - r.sx) * r.dx, (p.y - r.sy) * r.dy)
    const w1 = Math.max(8, Math.min(canvasSize, Math.round(r.startW + d)))
    const h1 = Math.max(8, Math.min(canvasSize, Math.round(w1 * (layer.h / layer.w))))
    const dw = w1 - r.startW
    const dh = h1 - r.startH
    const maxX = Math.max(0, canvasSize - w1)
    const maxY = Math.max(0, canvasSize - h1)
    const x1 = Math.max(0, Math.min(r.dx === -1 ? Math.round(r.startX - dw) : layer.x, maxX))
    const y1 = Math.max(0, Math.min(r.dy === -1 ? Math.round(r.startY - dh) : layer.y, maxY))
    emit('update', { ...layer, x: x1, y: y1, scale_w: w1, scale_h: h1 })
  }
}

function onPointerUp() {
  drag.value = null
  resize.value = null
}
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
      <template v-if="layer.id === selectedId">
        <span class="resizer nw" @pointerdown.stop="(e) => onResizeStart(e, layer, -1, -1)"></span>
        <span class="resizer ne" @pointerdown.stop="(e) => onResizeStart(e, layer, 1, -1)"></span>
        <span class="resizer sw" @pointerdown.stop="(e) => onResizeStart(e, layer, -1, 1)"></span>
        <span class="resizer se" @pointerdown.stop="(e) => onResizeStart(e, layer, 1, 1)"></span>
      </template>
    </div>
  </div>
</template>

<style scoped>
.canvas {
  position: relative;
  width: 512px;
  height: 512px;
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='512' height='512'><line x1='0' y1='256' x2='512' y2='256' stroke='rgba(200,70,50,0.45)' stroke-width='1.5'/><line x1='256' y1='0' x2='256' y2='512' stroke='rgba(200,70,50,0.45)' stroke-width='1.5'/><line x1='0' y1='0' x2='512' y2='512' stroke='rgba(200,70,50,0.45)' stroke-width='1.5' stroke-dasharray='14 12'/><line x1='512' y1='0' x2='0' y2='512' stroke='rgba(200,70,50,0.45)' stroke-width='1.5' stroke-dasharray='14 12'/></svg>");
  background-color: #fff8ec;
  border: 1px solid rgba(200, 70, 50, 0.7);
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
.resizer {
  position: absolute;
  width: 10px;
  height: 10px;
  border: 2px solid #2b7de9;
  background: #fff;
  box-sizing: border-box;
  z-index: 2;
}
.resizer.nw {
  left: -6px;
  top: -6px;
  cursor: nwse-resize;
}
.resizer.ne {
  right: -6px;
  top: -6px;
  cursor: nesw-resize;
}
.resizer.sw {
  left: -6px;
  bottom: -6px;
  cursor: nesw-resize;
}
.resizer.se {
  right: -6px;
  bottom: -6px;
  cursor: nwse-resize;
}
</style>
