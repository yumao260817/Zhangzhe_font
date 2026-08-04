<script setup>
import { ref, onMounted } from 'vue'
import { api, getToken } from '../auth.js'

const items = ref([])
const tab = ref('pending')
const loading = ref(false)
const message = ref('')

async function load() {
  loading.value = true
  message.value = ''
  try {
    const res = await api(`/api/candidates?status=${tab.value}`)
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      message.value = body.detail || '加载失败'
      items.value = []
      return
    }
    items.value = await res.json()
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

function imgUrl(uid) {
  return `/api/candidates/${uid}/png${authQuery()}`
}

function svgUrl(uid) {
  return `/api/candidates/${uid}/svg${authQuery()}`
}

async function act(uid, action) {
  message.value = ''
  const fd = new FormData()
  fd.append('uid', uid)
  const res = await api(`/api/admin/${action}`, { method: 'POST', body: fd })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    message.value = body.detail || `${action} 失败`
    return
  }
  await load()
}

onMounted(load)
</script>

<template>
  <div class="admin">
    <h2>管理员审核</h2>
    <div class="tabs">
      <button :class="{ active: tab === 'pending' }" @click="tab = 'pending'; load()">待审核</button>
      <button :class="{ active: tab === 'approved' }" @click="tab = 'approved'; load()">已批准</button>
      <button :class="{ active: tab === 'rejected' }" @click="tab = 'rejected'; load()">已驳回</button>
    </div>
    <p v-if="message" class="msg">{{ message }}</p>
    <p v-if="loading">加载中…</p>
    <p v-else-if="!items.length" class="empty">列表为空</p>
    <div v-else class="grid">
      <div v-for="c in items" :key="c.uid" class="card">
        <img :src="imgUrl(c.uid)" :alt="c.char" />
        <div class="info">
          <div class="big">「{{ c.char }}」</div>
          <div>{{ c.author || '佚名' }} · {{ c.created_at?.slice(0, 10) }}</div>
          <div v-if="c.note" class="note">{{ c.note }}</div>
          <div class="row">
            <a :href="imgUrl(c.uid)" target="_blank">PNG</a>
            <a :href="svgUrl(c.uid)" target="_blank">SVG</a>
          </div>
        </div>
        <div v-if="tab === 'pending'" class="acts">
          <button class="ok" @click="act(c.uid, 'approve')">通过</button>
          <button class="no" @click="act(c.uid, 'reject')">驳回</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.admin {
  padding: 20px;
  max-width: 1100px;
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
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 14px;
}
.card {
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 10px;
  background: #fff;
}
.card img {
  width: 100%;
  aspect-ratio: 1;
  object-fit: contain;
  background: linear-gradient(45deg, #f2f2f2 25%, transparent 25%, transparent 75%, #f2f2f2 75%),
    linear-gradient(45deg, #f2f2f2 25%, #fff 25%, #fff 75%, #f2f2f2 75%);
  background-size: 16px 16px;
  border-radius: 4px;
}
.info {
  font-size: 13px;
  color: #444;
  margin: 8px 0;
}
.info .big {
  font-size: 15px;
  font-weight: 700;
  color: #222;
}
.note {
  color: #8a6d3b;
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
  gap: 6px;
}
.acts .ok {
  background: #2e7d32;
  color: #fff;
}
.acts .no {
  background: #c62828;
  color: #fff;
}
button {
  padding: 6px 12px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}
.empty {
  color: #999;
}
.msg {
  color: #c62828;
}
</style>
