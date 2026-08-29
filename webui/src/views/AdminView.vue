<script setup>
import { ref, computed, onMounted } from 'vue'
import { api, getToken } from '../auth.js'

const items = ref([])
const tab = ref('pending')
const loading = ref(false)
const message = ref('')
const todo = ref(null)
const selected = ref(new Set())
const light = ref(null)

async function load() {
  loading.value = true
  message.value = ''
  selected.value = new Set()
  try {
    if (tab.value === 'todo') {
      const res = await api('/api/admin/todo')
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || '加载失败')
      }
      todo.value = await res.json()
      items.value = []
      return
    }
    const res = await api(`/api/candidates?status=${tab.value}`)
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      message.value = body.detail || '加载失败'
      items.value = []
      return
    }
    items.value = (await res.json()).map((x) => ({ ...x, noteInput: '' }))
  } catch (err) {
    message.value = `加载失败: ${err.message}`
    items.value = []
  } finally {
    loading.value = false
  }
}

function authQuery() {
  const t = getToken()
  return t ? `?token=${encodeURIComponent(t)}` : ''
}

function goHome() {
  window.location.hash = '#/gallery'
}

function openChar(ch) {
  window.location.hash = `#/workspace/${encodeURIComponent(ch)}`
}

function imgUrl(uid) {
  return `/api/candidates/${uid}/png${authQuery()}`
}

function svgUrl(uid) {
  return `/api/candidates/${uid}/svg${authQuery()}`
}

function sourceUrl(uid) {
  return `/api/candidates/${uid}/source${authQuery()}`
}

function onImgErr(e) {
  e.target.style.display = 'none'
}

function enlarge(c, isSource) {
  light.value = isSource ? sourceUrl(c.uid) : imgUrl(c.uid)
}

const allSelected = computed({
  get() {
    return items.value.length > 0 && items.value.every((c) => selected.value.has(c.uid))
  },
  set(v) {
    const s = new Set(selected.value)
    for (const c of items.value) {
      if (v) s.add(c.uid)
      else s.delete(c.uid)
    }
    selected.value = s
  },
})

function toggle(uid) {
  const s = new Set(selected.value)
  if (s.has(uid)) s.delete(uid)
  else s.add(uid)
  selected.value = s
}

async function act(uid, action, note) {
  const fd = new FormData()
  fd.append('uid', uid)
  if (note) fd.append('note', note)
  const res = await api(`/api/admin/${action}`, { method: 'POST', body: fd })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    message.value = body.detail || `${action} 失败`
    return false
  }
  return true
}

async function singleAct(c, action) {
  const ok = await act(c.uid, action, c.noteInput || '')
  if (ok) await load()
}

async function batch(action) {
  const uids = [...selected.value]
  if (!uids.length) {
    message.value = '请先勾选候选'
    return
  }
  message.value = `正在${action === 'approve' ? '通过' : '驳回'} ${uids.length} 项…`
  await Promise.all(uids.map((uid) => act(uid, action, '')))
  await load()
}

onMounted(load)
</script>

<template>
  <div class="admin">
    <div class="head">
      <h2>管理员审核</h2>
      <button class="primary" @click="goHome">返回首页</button>
    </div>
    <div class="tabs">
      <button :class="{ active: tab === 'todo' }" @click="tab = 'todo'; load()">待办</button>
      <button :class="{ active: tab === 'pending' }" @click="tab = 'pending'; load()">待审核</button>
      <button :class="{ active: tab === 'approved' }" @click="tab = 'approved'; load()">已过审</button>
      <button :class="{ active: tab === 'rejected' }" @click="tab = 'rejected'; load()">已驳回</button>
    </div>
    <p v-if="message" class="msg">{{ message }}</p>
    <p v-if="loading">加载中…</p>

    <template v-if="tab === 'todo' && todo">
      <div class="todo-sum">
        <p>缺字总数：<b>{{ todo.missing_count }}</b>（含待拼与已有候选未过审）</p>
        <div v-if="todo.pending_by_char.length" class="todo-pending">
          <h3>已有候选待审核</h3>
          <div class="pending-chips">
            <button v-for="p in todo.pending_by_char" :key="p.char" class="chip" @click="openChar(p.char)">
              {{ p.char }} ×{{ p.count }}
            </button>
          </div>
        </div>
        <h3>缺字列表（前 200）</h3>
        <div class="missing-box">
          <button v-for="c in todo.missing.slice(0, 200)" :key="c" class="chip" @click="openChar(c)">{{ c }}</button>
        </div>
      </div>
    </template>

    <template v-else>
      <div v-if="tab === 'pending' && items.length" class="toolbar">
        <label class="sel-all"><input type="checkbox" v-model="allSelected" /> 全选</label>
        <button class="ok" @click="batch('approve')">批量通过 ({{ selected.size }})</button>
        <button class="no" @click="batch('reject')">批量驳回 ({{ selected.size }})</button>
      </div>
      <p v-if="!loading && !items.length" class="empty">列表为空</p>
      <div v-else class="row-scroll">
        <div
          v-for="c in items"
          :key="c.uid"
          class="card"
          :class="{ selected: selected.has(c.uid) }"
        >
          <div class="card-check">
            <input type="checkbox" :checked="selected.has(c.uid)" @change="toggle(c.uid)" />
          </div>
          <div class="imgs">
            <span class="src-tag" :class="c.source === 'original' ? 'orig' : 'comp'">
              {{ c.source === 'original' ? '原字' : '拼字' }}
            </span>
            <div class="img-wrap" @click="enlarge(c, false)">
              <span class="cap">候选</span>
              <img :src="imgUrl(c.uid)" :alt="c.char" @error="onImgErr" />
            </div>
            <div class="img-wrap" @click="enlarge(c, true)" v-if="c.source === 'original'">
              <span class="cap">出处原图</span>
              <img :src="sourceUrl(c.uid)" :alt="c.char + ' 出处'" @error="onImgErr" />
            </div>
            <div class="img-wrap placeholder" v-else>
              <span class="cap">出处原图</span>
              <span class="ph-text">暂无出处</span>
            </div>
          </div>
          <div class="side">
            <div class="info">
              <div class="big">「{{ c.char }}」</div>
              <div class="meta">{{ c.author || '佚名' }} · {{ c.created_at?.slice(0, 10) }}</div>
              <div class="row">
                <a :href="imgUrl(c.uid)" target="_blank">PNG</a>
                <a :href="svgUrl(c.uid)" target="_blank">SVG</a>
              </div>
            </div>
            <div class="acts">
              <button class="ok" @click="singleAct(c, 'approve')">通过</button>
              <button class="no" @click="singleAct(c, 'reject')">驳回</button>
            </div>
            <textarea v-model="c.noteInput" class="note-input" placeholder="批注（可选）"></textarea>
          </div>
        </div>
      </div>
    </template>

    <div v-if="light" class="lightbox" @click="light = null">
      <img :src="light" @error="onImgErr" />
      <span class="close">点击任意处关闭</span>
    </div>
  </div>
</template>

<style scoped>
.admin {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}
.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.head h2 {
  margin: 0 0 14px;
}
.head .primary {
  padding: 6px 12px;
  border: 1px solid #2b7de9;
  border-radius: 4px;
  background: #2b7de9;
  color: #fff;
  cursor: pointer;
  font-size: 14px;
}
.head .primary:hover {
  background: #1f66c4;
}
.tabs {
  display: flex;
  gap: 6px;
  margin-bottom: 14px;
}
.tabs button {
  padding: 6px 14px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background: #fff;
  cursor: pointer;
}
.tabs button.active {
  background: #2b7de9;
  color: #fff;
  border-color: #2b7de9;
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.toolbar .sel-all {
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 4px;
}
.toolbar button {
  padding: 6px 14px;
  border: none;
  border-radius: 4px;
  color: #fff;
  cursor: pointer;
}
.toolbar .ok { background: #2e7d32; }
.toolbar .no { background: #c62828; }
.row-scroll {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}
.card {
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 10px;
  background: #fff;
  display: flex;
  flex-direction: row;
  align-items: stretch;
  gap: 12px;
}
.card.selected {
  border-color: #2b7de9;
  box-shadow: 0 0 0 2px rgba(43, 125, 233, 0.25);
}
.card-check {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 28px;
}
.imgs {
  position: relative;
  display: flex;
  gap: 8px;
  align-items: stretch;
  max-width: 224px;
}
.img-wrap {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  cursor: zoom-in;
}
.img-wrap .cap {
  font-size: 11px;
  color: #888;
  text-align: center;
  margin-bottom: 2px;
}
.img-wrap img {
  width: 100%;
  height: 100%;
  min-height: 0;
  flex: 1;
  object-fit: contain;
  background: linear-gradient(45deg, #f2f2f2 25%, transparent 25%, transparent 75%, #f2f2f2 75%),
    linear-gradient(45deg, #f2f2f2 25%, #fff 25%, #fff 75%, #f2f2f2 75%);
  background-size: 16px 16px;
  border-radius: 4px;
}
.img-wrap.placeholder {
  cursor: default;
  align-items: center;
  justify-content: center;
  border: 1px dashed #ccc;
  border-radius: 4px;
  background: #fafafa;
  height: 100%;
  min-height: 0;
}
.img-wrap.placeholder .ph-text {
  color: #bbb;
  font-size: 12px;
}
.side {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.info {
  font-size: 13px;
  color: #444;
  margin: 0;
  min-width: 0;
}
.info .big {
  font-size: 16px;
  font-weight: 700;
  color: #222;
}
.info .meta {
  color: #888;
  margin: 2px 0 4px;
}
.note-input {
  width: 100%;
  height: 60px;
  resize: none;
  overflow-y: auto;
  margin-top: auto;
  font-size: 12px;
  padding: 4px 6px;
  border: 1px solid #ddd;
  border-radius: 4px;
  box-sizing: border-box;
}
.row {
  display: flex;
  gap: 10px;
  margin-top: 4px;
}
.row a {
  color: #2b7de9;
}
.acts {
  display: flex;
  flex-direction: row;
  gap: 6px;
}
.acts button {
  flex: 1;
  padding: 6px 0;
  border: none;
  border-radius: 4px;
  color: #fff;
  cursor: pointer;
}
.acts .ok { background: #2e7d32; }
.acts .no { background: #c62828; }
.src-tag {
  position: absolute;
  top: 2px;
  left: 2px;
  z-index: 2;
  font-size: 11px;
  font-weight: 400;
  color: #fff;
  padding: 1px 6px;
  border-radius: 3px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
}
.src-tag.orig { background: #2b7de9; }
.src-tag.comp { background: #c62828; }
.empty { color: #999; }
.msg { color: #c62828; }
.todo-sum h3 { margin: 14px 0 8px; font-size: 14px; }
.pending-chips, .missing-box {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.chip {
  padding: 4px 9px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background: #f5f6f8;
  cursor: pointer;
  font-size: 14px;
}
.chip:hover { background: #e3ecfa; border-color: #2b7de9; }
.lightbox {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  cursor: zoom-out;
}
.lightbox img {
  max-width: 90vw;
  max-height: 85vh;
  background: #fff;
  border-radius: 6px;
}
.lightbox .close {
  color: #fff;
  margin-top: 12px;
  font-size: 13px;
  opacity: 0.8;
}
</style>
