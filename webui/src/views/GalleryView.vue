<script setup>
import { ref, onMounted, computed, watch } from 'vue'

const emit = defineEmits(['open-char'])

const all = ref([])
const loading = ref(true)
const error = ref('')
const filter = ref('all') // all | done | missing
const query = ref('')
const pyChars = ref([]) // 拼音命中的字
const pyName = ref('') // 当前拼音（显示提示用）

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

function isPinyin(q) {
  return /^[a-zA-Z]+$/.test(q)
}

let timer = null
watch(query, (q) => {
  clearTimeout(timer)
  q = q.trim()
  if (isPinyin(q)) {
    timer = setTimeout(async () => {
      try {
        const res = await fetch(`/api/pinyin/${encodeURIComponent(q.toLowerCase())}`)
        if (!res.ok) return
        const data = await res.json()
        if (data.pinyin !== q.toLowerCase()) return // 输入已变化
        pyChars.value = data.chars
        pyName.value = data.pinyin
      } catch (e) {
        pyChars.value = []
      }
    }, 200)
  } else {
    pyChars.value = []
    pyName.value = ''
  }
})

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
  if (q) {
    if (isPinyin(q)) {
      const keys = new Set(pyChars.value.map((c) => c.char))
      list = list.filter((c) => keys.has(c.char))
    } else {
      list = list.filter((c) => q.includes(c.char))
    }
  }
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

function scrollTop() {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

onMounted(loadAll)
</script>

<template>
  <div>
    <div class="toolbar">
      <h2>字库（{{ stats.total }} 字 / 已有 {{ stats.done }}）</h2>
      <input v-model="query" placeholder="输入汉字或拼音，如：张 / zhang" />
      <span v-if="pyName" class="pynote">拼音「{{ pyName }}」共 {{ pyChars.length }} 字</span>
      <div class="filters">
        <button :class="{ active: filter === 'all' }" @click="filter = 'all'">全部</button>
        <button :class="{ active: filter === 'done' }" @click="filter = 'done'">已有</button>
        <button :class="{ active: filter === 'missing' }" @click="filter = 'missing'">待做</button>
      </div>
    </div>
    <div class="gallery">
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
        <span
          v-if="c.handwritten || c.approved_uid"
          class="src-tag"
          :class="c.handwritten || c.approved_source === 'original' ? 'orig' : 'comp'"
          >{{ c.handwritten || c.approved_source === 'original' ? '原字' : '拼字' }}</span
        >
      </button>
    </div>

    <button class="back-top" @click="scrollTop">回到顶部</button>
    </div>
  </div>
</template>

<style scoped>
.gallery {
  padding: 20px;
  max-width: 1240px;
  margin: 0 auto;
}
.toolbar {
  position: sticky;
  top: 52px;
  z-index: 90;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  flex-wrap: wrap;
  background: #f5f6f8;
  padding: 10px 20px;
  border-bottom: 1px solid #e0e0e0;
}
.toolbar h2 {
  margin: 0;
  font-size: 16px;
}
.toolbar input {
  width: 200px;
  padding: 7px;
  border: 1px solid #ccc;
  border-radius: 4px;
}
.pynote {
  font-size: 12px;
  color: #2b7de9;
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
  column-width: 120px;
  column-gap: 8px;
}
.cell {
  position: relative;
  display: block;
  width: 100%;
  margin: 0 0 8px;
  padding: 0;
  border: 1px solid #e0e0e0;
  border-radius: 5px;
  background: #fff;
  cursor: pointer;
  overflow: hidden;
  break-inside: avoid;
}
.cell:hover {
  border-color: #2b7de9;
  box-shadow: 0 0 0 2px rgba(43, 125, 233, 0.25);
}
.cell img {
  width: 100%;
  aspect-ratio: 1 / 1;
  object-fit: contain;
  display: block;
}
.cell.has {
  border-color: #c8d9f5;
}
.lbl {
  position: absolute;
  left: 3px;
  bottom: 2px;
  font-size: 12px;
  color: #888;
  background: rgba(255, 255, 255, 0.75);
  padding: 0 4px;
  border-radius: 2px;
  pointer-events: none;
  font-family: SimSun, 宋体, serif;
}
.src-tag {
  position: absolute;
  right: 3px;
  bottom: 2px;
  font-size: 11px;
  padding: 0 4px;
  border-radius: 2px;
  pointer-events: none;
  color: #fff;
}
.src-tag.orig {
  background: rgba(43, 125, 233, 0.85);
}
.src-tag.comp {
  background: rgba(198, 40, 40, 0.85);
}
.err {
  color: #c62828;
}
.back-top {
  position: fixed;
  right: 280px;
  bottom: 7vh;
  z-index: 10;
  padding: 8px 24px;
  border: 1px solid #2b7de9;
  border-radius: 20px;
  background: #2b7de9;
  color: #fff;
  cursor: pointer;
  font-size: 13px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
}
.back-top:hover {
  background: #1f66c4;
}
</style>