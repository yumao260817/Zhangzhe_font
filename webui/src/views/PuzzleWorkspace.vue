<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import LayerCanvas from '../components/LayerCanvas.vue'
import { renderCanvas } from '../utils/paint.js'
import { api } from '../auth.js'

const props = defineProps({
  initialChar: { type: String, default: '' },
})
const emit = defineEmits(['char-changed'])

const layers = ref([])
const selectedId = ref(null)
const char = ref('')
const note = ref('')
const charInfo = ref(null)
const loading = ref(false)
const message = ref('')
const exporting = ref(false)
const pendingChars = ref([])
const sourceImg = ref(null)
const sourceName = ref('')

let seq = 0

function addKey() {
  return 'loc-' + ++seq + '-' + Date.now()
}

function readFileAsDataURL(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result)
    reader.onerror = () => reject(new Error('文件读取失败'))
    reader.readAsDataURL(file)
  })
}

async function uploadFiles(fileList) {
  for (const file of fileList) {
    try {
      // 部件仅在前端处理，不上传后台
      const url = await readFileAsDataURL(file)
      const img = new Image()
      await new Promise((resolve, reject) => {
        img.onload = resolve
        img.onerror = () => reject(new Error('图片解析失败'))
        img.src = url
      })
      const id = addKey()
      layers.value.push({
        id,
        url,
        w: img.naturalWidth,
        h: img.naturalHeight,
        x: 180,
        y: 180,
        scale_w: img.naturalWidth,
        scale_h: img.naturalHeight,
        angle: 0,
        flip: false,
      })
      selectedId.value = id
    } catch (err) {
      message.value = `${file.name}: ${err.message}`
    }
  }
}

function onFileChange(e) {
  uploadFiles(e.target.files)
}

async function onSourceChange(e) {
  const file = e.target.files && e.target.files[0]
  if (!file) return
  try {
    sourceImg.value = await compressImage(file)
    sourceName.value = file.name
    message.value = ''
  } catch (err) {
    sourceImg.value = null
    sourceName.value = ''
    message.value = `出处图读取失败: ${err.message}`
  }
}

// 压缩：最长边限制 1024，转 PNG blob
async function compressImage(file) {
  const url = await readFileAsDataURL(file)
  const img = new Image()
  await new Promise((resolve, reject) => {
    img.onload = resolve
    img.onerror = () => reject(new Error('图片解析失败'))
    img.src = url
  })
  const MAX = 1024
  let { naturalWidth: w, naturalHeight: h } = img
  if (w > MAX || h > MAX) {
    const k = Math.min(MAX / w, MAX / h)
    w = Math.round(w * k)
    h = Math.round(h * k)
  }
  const canvas = document.createElement('canvas')
  canvas.width = w
  canvas.height = h
  canvas.getContext('2d').drawImage(img, 0, 0, w, h)
  const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/png'))
  if (!blob) throw new Error('压缩失败')
  return blob
}

function dropHandler(e) {
  e.preventDefault()
  if (e.dataTransfer && e.dataTransfer.files.length) uploadFiles(e.dataTransfer.files)
}

const selected = computed(() => layers.value.find((l) => l.id === selectedId.value) || null)

function updateLayer(next) {
  const i = layers.value.findIndex((l) => l.id === next.id)
  if (i >= 0) layers.value[i] = next
}

function deleteLayer(id) {
  layers.value = layers.value.filter((l) => l.id !== id)
  if (selectedId.value === id) selectedId.value = null
}

function zMove(delta) {
  const i = layers.value.findIndex((l) => l.id === selectedId.value)
  if (i < 0) return
  const j = i + delta
  if (j < 0 || j >= layers.value.length) return
  const arr = [...layers.value]
  const [item] = arr.splice(i, 1)
  arr.splice(j, 0, item)
  layers.value = arr
}

function settleIntoCenter() {
  // 将各图层按原始尺寸居中铺到画布，便于初始布局
  layers.value = layers.value.map((l, idx) => ({
    ...l,
    x: 0,
    y: 0,
    scale_w: l.w,
    scale_h: l.h,
  }))
}

async function queryChar() {
  const c = char.value.trim()
  if (!c) return
  loading.value = true
  message.value = ''
  emit('char-changed', c)
  try {
    const res = await fetch(`/api/char/${encodeURIComponent(c)}`)
    charInfo.value = res.ok ? await res.json() : null
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      message.value = body.detail || '查询失败'
    }
  } catch (err) {
    message.value = `查询失败: ${err.message}`
  } finally {
    loading.value = false
  }
}

async function loadPending() {
  try {
    const res = await fetch('/api/random-pending?n=5')
    pendingChars.value = res.ok ? await res.json() : []
  } catch {
    pendingChars.value = []
  }
}

function usePending(ch) {
  char.value = ch
  note.value = ''
  queryChar()
}

watch(
  () => props.initialChar,
  (c) => {
    if (c) {
      char.value = c
      queryChar()
    }
  },
  { immediate: true },
)

onMounted(loadPending)

async function exportLayer() {
  if (!char.value.trim()) {
    message.value = '请先输入目标字'
    return
  }
  if (!layers.value.length) {
    message.value = '画布为空'
    return
  }
  exporting.value = true
  message.value = ''
  try {
    // 所见即所得：把当前画布渲染成 PNG，仅提交合并后的图片（部件不落服务器）
    const canvas = await renderCanvas(layers.value)
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/png'))
    const fd = new FormData()
    fd.append('note', note.value)
    fd.append('file', blob, 'render.png')
    if (sourceImg.value) fd.append('source', sourceImg.value, 'source.png')
    const res = await api(`/api/char/${encodeURIComponent(char.value.trim())}/submit`, { method: 'POST', body: fd })
    const body = await res.json()
    if (!res.ok) throw new Error(body.detail || '导出失败')
    message.value = `已提交 ${body.char} 候选（待管理员审核）`
    await queryChar()
  } catch (err) {
    message.value = `导出失败: ${err.message}`
  } finally {
    exporting.value = false
  }
}

function reset() {
  layers.value = []
  selectedId.value = null
  note.value = ''
  sourceImg.value = null
  sourceName.value = ''
}

function goGallery() {
  window.location.hash = '#/gallery'
}
</script>

<template>
  <div class="workspace">
    <div class="left">
      <div class="field">
        <label>目标字</label>
        <div class="row">
          <input v-model="char" maxlength="1" placeholder="如：张" @keyup.enter="queryChar" />
          <button @click="queryChar" :disabled="loading">查询</button>
        </div>
        <div v-if="charInfo" class="charinfo">
          <span :class="charInfo.handwritten ? 'ok' : 'no'">
            {{ charInfo.handwritten ? '已有手写原迹' : '缺手写' }}
          </span>
          <span>待审 {{ charInfo.pending.length }} / 已过审 {{ charInfo.approved.length }}</span>
        </div>
      </div>

      <div class="field">
        <label class="upload-btn">
          添加部件
          <input type="file" accept="image/png" multiple @change="onFileChange" />
        </label>
        <p class="hint">你可以直接上传白底黑字的整字<br>也可以用偏旁部首拼接<br>支持多选，或直接拖拽到画布中</p>
      </div>

      <div class="field">
        <label class="upload-btn source-btn">
          上传出处
          <input type="file" accept="image/*" @change="onSourceChange" />
        </label>
        <p class="hint">此处上传整字原图作为审核证据（可选，过大将自动压缩）；未上传出处原图的无论是整字还是拼字将一律标记为「拼字」</p>
        <p v-if="sourceName" class="source-note">已上传出处原图：{{ sourceName }}</p>
      </div>

      <p class="hint">点击画布中的图层可选中操作</p>
      <button class="primary" @click="goGallery">返回首页</button>
    </div>

    <div class="right">
      <div class="canvas-area">
        <div
          class="canvas-host"
          @dragover.prevent
          @drop="dropHandler"
        >
          <LayerCanvas
            :layers="layers"
            :selected-id="selectedId"
            :reference-url="charInfo && charInfo.std ? `/api/std/${encodeURIComponent(charInfo.char)}/img` : null"
            @select="(id) => (selectedId = id)"
            @update="updateLayer"
            @delete="deleteLayer"
          />
        </div>

        <div v-if="selected" class="tools">
          <h3>图层工具（滚轮缩放 / 拖动挪位）</h3>
          <p>
            原始 {{ selected.w }}×{{ selected.h }}
            <span v-if="selected.scale_w !== selected.w || selected.scale_h !== selected.h">
              → 显示 {{ selected.scale_w }}×{{ selected.scale_h }}
            </span>
          </p>
          <div class="row">
            <input
              type="range"
              min="10"
              max="400"
              :value="selected.scale_w"
              @input="updateLayer({ ...selected, scale_w: +$event.target.value, scale_h: Math.round(+$event.target.value * (selected.h / selected.w)) })"
            />
          </div>
          <div class="row">
            <button @click="updateLayer({ ...selected, flip: !selected.flip })">翻转</button>
            <button @click="updateLayer({ ...selected, angle: (selected.angle + 90) % 360 })">旋转90°</button>
            <button @click="updateLayer({ ...selected, angle: (selected.angle - 90) % 360 })">反向90°</button>
            <button class="danger" @click="deleteLayer(selected.id)">删除</button>
          </div>
          <div class="row">
            <button @click="selected && zMove(1)">置上</button>
            <button @click="selected && zMove(-1)">置下</button>
            <button @click="settleIntoCenter">全部归零</button>
          </div>
        </div>
      </div>
      <div class="exportbar">
        <!-- <input v-model="note" placeholder="备注（可选）" /> -->
        <button class="primary" @click="exportLayer" :disabled="exporting">
          {{ exporting ? '提交中…' : '提交' }}
        </button>
        <button class="btn-clear" @click="reset">清空</button>
      </div>
      <p v-if="message" :class="message.startsWith('已') ? 'msg-ok' : 'msg-err'">{{ message }}</p>
    </div>

    <div v-if="pendingChars.length" class="pending-banner">
      <span class="pb-label">你也许还想试试：</span>
      <button v-for="c in pendingChars" :key="c.char" class="pb-char" @click="usePending(c.char)">
        {{ c.char }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.workspace {
  display: flex;
  gap: 20px;
  padding: 20px;
  flex-wrap: wrap;
}
.pending-banner {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  background: #fff8e1;
  border: 1px solid #ffe082;
  border-radius: 8px;
  padding: 10px 14px;
}
.pb-label {
  font-size: 13px;
  color: #795548;
  font-weight: 600;
}
.pb-char {
  width: 44px;
  height: 44px;
  font-size: 24px;
  border: 1px solid #ffb300;
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
  font-family: SimSun, 宋体, serif;
}
.pb-char:hover {
  background: #ffe0b2;
}
.left {
  flex: 0 0 280px;
  display: flex;
  flex-direction: column;
}
.left .field,
.left .tools,
.left > .hint {
  flex-shrink: 0;
}
.left > button {
  margin-top: auto;
}
.field {
  margin-bottom: 16px;
}
.field label {
  display: block;
  font-weight: 600;
  margin-bottom: 6px;
  font-size: 14px;
}
.row {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
input[type='text'],
input:not([type]) {
  padding: 6px 8px;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-size: 14px;
}
input[type='range'] {
  width: 100%;
}
button {
  padding: 6px 12px;
  border: 1px solid #bbb;
  border-radius: 4px;
  background: #f6f6f6;
  cursor: pointer;
}
button.primary {
  background: #2b7de9;
  color: #fff;
  border-color: #2b7de9;
}
button.danger {
  color: #c62828;
}
.charinfo {
  display: flex;
  gap: 10px;
  font-size: 13px;
  margin-top: 6px;
}
.ok {
  color: #2e7d32;
}
.no {
  color: #c62828;
  font-weight: 700;
}
.tools {
  background: #fafafa;
  border: 1px solid #eee;
  border-radius: 6px;
  padding: 10px;
}
.tools h3 {
  margin: 0 0 6px;
  font-size: 13px;
}
.hint {
  color: #888;
  font-size: 13px;
}
.field label.upload-btn {
  display: inline-block;
  width: auto;
  padding: 6px 12px;
  border: 1px solid #2b7de9;
  border-radius: 4px;
  background: #2b7de9;
  color: #fff;
  cursor: pointer;
  font-size: 14px;
}
.upload-btn input[type='file'] {
  display: none;
}
.source-btn {
  background: #6a4fa3;
  border-color: #6a4fa3;
}
.source-note {
  font-size: 13px;
  color: #2e7d32;
  margin-top: 4px;
}
.btn-clear {
  background: #c62828;
  color: #fff;
  border-color: #c62828;
}
.right {
  flex: 1;
  min-width: 520px;
}
.canvas-host {
  display: inline-block;
}
.canvas-area {
  display: flex;
  gap: 14px;
  align-items: flex-start;
}
.canvas-area .tools {
  flex: 0 0 220px;
}
.exportbar {
  display: flex;
  gap: 8px;
  margin-top: 14px;
  flex-wrap: wrap;
}
.exportbar input {
  flex: 1;
  min-width: 120px;
}
.msg-ok {
  color: #2e7d32;
}
.msg-err {
  color: #c62828;
}
</style>