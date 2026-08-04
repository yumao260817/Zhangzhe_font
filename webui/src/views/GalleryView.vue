<script setup>
import { ref, onMounted, computed } from 'vue'

const emit = defineEmits(['open-char'])

const all = ref([])
const loading = ref(true)
const error = ref('')
const filter = ref('all') // all | done | missing
const query = ref('')

async function loadAll() {
  loading.value = true
  error.value = ''
  try {
    const res = await fetch('/api/gallery')
    if (!res.ok) throw new Error(`加载失败 ${res.status}`)
    all.value = await res.json()
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}

const stats = computed(() => {
  if (!all.value.length) return { total: 0, done: 0 }
  const done = all.value.filter((c) => c.handwritten || c.approved_uid).length
  return { total: all.value.length, done }
})

const shown = computed(() => {
  let list = all.value
  if (filter.value === 'done') list = list.filter((c) => c.handwritten || c.approved_uid)
  if (filter.value === 'missing') list = list.filter((c) => !c.handwritten && !c.approved_uid)
  const q = query.value.trim()
  if (q) list = list.filter((c) => c.char === q)
  return list
})

function imgUrl(c) {
  if (c.handwritten) return `/api/hand/${encodeURIComponent(c.char)}/img`
  if (c.approved_uid) return `/api/candidates/${c.approved_uid}/png`
  return null
}

// 占位：半透明宋体字（data URI，零请求）
const PLACEHOLDER = 'data:image/svg+xml;utf8,'
function placeholder(c) {
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128">` +
    `<rect width="128" height="128" fill="transparent"/>` +
    `<text x="64" y="92" font-size="84" text-anchor="middle" fill="#000" opacity="0.22" font-family="SimSun,宋体,serif">${c.char}</text>` +
    `</svg>`
  return PLACEHOLDER + encodeURIComponent(svg)
}

function open(c) {
  emit('open-char', c.char)
}

onMounted(loadAll)
</script>

<template>
  <div class="gallery">
    <div class="toolbar">
      <h2>字库（{{ stats.total }} 字 / 已有 {{ stats.done }}）</h2>
      <input v-model="query" maxlength="1" placeholder="过滤：输入汉字" />
      <div class="filters">
        <button :class="{ active: filter === 'all' }" @click="filter = 'all'">全部</button>
        <button :class="{ active: filter === 'done' }" @click="filter = 'done'">已有</button>
        <button :class="{ active: filter === 'missing' }" @click="filter = 'missing'">待做</button>
      </div>
    </div>
    <p v-if="loading">加载中…</p>
    <p v-if="error" class="err">错误：{{ error }}</p>

    <div v-else class="grid">
      <button
        v-for="c in shown"
        :key="c.char"
        class="cell"
        :class="{ has: c.handwritten || c.approved_uid }"
        @click="open(c)"
      >
        <img
          v-if="c.handwritten || c.approved_uid"
          :src="imgUrl(c)"
          :alt="c.char"
          loading="lazy"
        />
        <img v-else :src="placeholder(c)" :alt="c.char" />
        <span class="lbl">{{ c.char }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.gallery {
  padding: 20px;
  max-width: 1200px;
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.toolbar h2 {
  margin: 0;
  font-size: 16px;
}
.toolbar input {
  width: 130px;
  padding: 7px;
  border: 1px solid #ccc;
  border-radius: 4px;
}
.filters {
  display: flex;
  gap: 6px;
}
.filters button {
  padding: 6px 14px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background: #fff;
  cursor: pointer;
}
.filters button.active {
  background: #2b7de9;
  color: #fff;
  border-color: #2b7de9;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(56px, 1fr));
  gap: 6px;
}
.cell {
  position: relative;
  padding: 0;
  border: 1px solid #e0e0e0;
  border-radius: 5px;
  background: #fff;
  cursor: pointer;
  aspect-ratio: 1;
  overflow: hidden;
}
.cell:hover {
  border-color: #2b7de9;
  box-shadow: 0 0 0 2px rgba(43, 125, 233, 0.25);
}
.cell img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
}
.cell.has {
  border-color: #c8d9f5;
}
.lbl {
  position: absolute;
  left: 2px;
  bottom: 1px;
  font-size: 10px;
  color: #888;
  background: rgba(255, 255, 255, 0.75);
  padding: 0 3px;
  border-radius: 2px;
  pointer-events: none;
  font-family: SimSun, 宋体, serif;
}
.err {
  color: #c62828;
}
</style>