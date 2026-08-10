<script setup>
import { ref, computed, onMounted } from 'vue'
import { api, getToken } from '../auth.js'

const props = defineProps({
  user: { type: Object, default: null },
})

const items = ref([])
const tab = ref('pending')
const loading = ref(false)
const message = ref('')

const isAdmin = computed(() => props.user && props.user.role === 'admin')

const users = ref([])
const usersLoading = ref(false)
const userMsg = ref('')

async function loadUsers() {
  if (!isAdmin.value) return
  usersLoading.value = true
  userMsg.value = ''
  try {
    const res = await api('/api/admin/users')
    if (!res.ok) {
      userMsg.value = (await res.json().catch(() => ({}))).detail || '成员加载失败'
      return
    }
    users.value = await res.json()
  } catch (err) {
    userMsg.value = `成员加载失败: ${err.message}`
  } finally {
    usersLoading.value = false
  }
}

async function setRole(email, role) {
  userMsg.value = ''
  const fd = new FormData()
  fd.append('email', email)
  fd.append('role', role)
  const res = await api('/api/admin/set-role', { method: 'POST', body: fd })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    userMsg.value = body.detail || '操作失败'
    return
  }
  await loadUsers()
}

const ROLE_LABEL = { admin: '管理员', reviewer: '审核员', user: '粉丝' }

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

function goHome() {
  window.location.hash = '#/gallery'
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

onMounted(() => {
  load()
  loadUsers()
})
</script>

<template>
  <div class="admin">
    <div class="head">
      <h2>管理员审核</h2>
      <button class="primary" @click="goHome">返回首页</button>
    </div>
    <div class="tabs">
      <button :class="{ active: tab === 'pending' }" @click="tab = 'pending'; load()">待审核</button>
      <button :class="{ active: tab === 'approved' }" @click="tab = 'approved'; load()">已过审</button>
      <button :class="{ active: tab === 'rejected' }" @click="tab = 'rejected'; load()">已驳回</button>
    </div>
    <div v-if="isAdmin" class="users">
      <h3>成员管理</h3>
      <p v-if="userMsg" class="msg">{{ userMsg }}</p>
      <p v-if="usersLoading">加载中…</p>
      <table v-else class="user-table">
        <thead>
          <tr>
            <th>昵称</th>
            <th>邮箱</th>
            <th>角色</th>
            <th>注册时间</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="u.id">
            <td>{{ u.name || '（未设置）' }}</td>
            <td>{{ u.email }}</td>
            <td><span class="role-badge" :class="`role-${u.role}`">{{ ROLE_LABEL[u.role] || u.role }}</span></td>
            <td>{{ u.created_at?.slice(0, 10) }}</td>
            <td>
              <button v-if="u.role === 'user'" class="ok" @click="setRole(u.email, 'reviewer')">提升审核员</button>
              <button v-else-if="u.role === 'reviewer'" class="no" @click="setRole(u.email, 'user')">降为粉丝</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-if="message" class="msg">{{ message }}</p>
    <p v-if="loading">加载中…</p>
    <p v-else-if="!items.length" class="empty">列表为空</p>
    <div v-else class="grid">
      <div v-for="c in items" :key="c.uid" class="card">
        <img :src="imgUrl(c.uid)" :alt="c.char" />
        <div class="info">
          <div class="big">
            「{{ c.char }}」
            <span class="src-tag" :class="c.source === 'original' ? 'orig' : 'comp'">
              {{ c.source === 'original' ? '原字' : '拼字' }}
            </span>
          </div>
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
.users {
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 14px 16px;
  margin-bottom: 16px;
}
.users h3 {
  margin: 0 0 10px;
  font-size: 15px;
}
.user-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.user-table th,
.user-table td {
  text-align: left;
  padding: 6px 8px;
  border-bottom: 1px solid #f0f0f0;
}
.role-badge {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 10px;
  color: #fff;
}
.role-admin {
  background: #2b7de9;
}
.role-reviewer {
  background: #6a4fa3;
}
.role-user {
  background: #888;
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
.src-tag {
  font-size: 11px;
  font-weight: 400;
  color: #fff;
  padding: 1px 6px;
  border-radius: 3px;
  margin-left: 6px;
}
.src-tag.orig {
  background: #2b7de9;
}
.src-tag.comp {
  background: #c62828;
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
