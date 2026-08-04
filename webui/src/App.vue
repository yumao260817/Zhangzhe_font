<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import PuzzleWorkspace from './views/PuzzleWorkspace.vue'
import GalleryView from './views/GalleryView.vue'
import AdminView from './views/AdminView.vue'
import AuthView from './views/AuthView.vue'
import { api, getToken, setToken } from './auth.js'

const view = ref('gallery')
const targetChar = ref('')
const health = ref(null)
const user = ref(null)

function parseHash() {
  const h = window.location.hash.replace(/^#\/?/, '')
  const [seg, ch] = h.split('/')
  if (seg === 'workspace') {
    view.value = 'workspace'
    targetChar.value = ch ? decodeURIComponent(ch) : ''
  } else if (seg === 'admin') {
    view.value = 'admin'
  } else if (seg === 'login') {
    view.value = 'login'
  } else {
    view.value = 'gallery'
  }
}

function navigate(seg, ch = '') {
  window.location.hash = ch ? `#/${seg}/${encodeURIComponent(ch)}` : `#/${seg}`
}

function openChar(ch) {
  navigate('workspace', ch)
}

function loadHealth() {
  fetch('/health')
    .then((r) => r.json())
    .then((h) => (health.value = h))
    .catch(() => (health.value = { ok: false }))
}

function restoreSession() {
  if (!getToken()) {
    user.value = null
    return
  }
  api('/api/auth/me')
    .then((r) => r.json())
    .then((d) => {
      if (d.user) user.value = d.user
      else {
        setToken('')
        user.value = null
      }
    })
    .catch(() => (user.value = null))
}

function onAuthed(u) {
  user.value = u
  navigate(u && u.role === 'admin' ? 'admin' : 'gallery')
}

function logout() {
  api('/api/auth/logout', { method: 'POST' }).finally(() => {
    setToken('')
    user.value = null
    navigate('gallery')
  })
}

onMounted(() => {
  parseHash()
  loadHealth()
  restoreSession()
  window.addEventListener('hashchange', parseHash)
})
onBeforeUnmount(() => window.removeEventListener('hashchange', parseHash))
</script>

<template>
  <div class="app">
    <header>
      <h1>手写字库 · 拼字工作台</h1>
      <span v-if="health && health.ok" class="conn ok">后端已连接</span>
      <span v-else class="conn no">后端未连接</span>
      <span v-if="user" class="who">
        {{ user.name || user.email }}
        <em v-if="user.role === 'admin'">（管理员）</em>
        <a href="#" @click.prevent="logout">退出</a>
      </span>
      <span v-else class="who">
        <a href="#/login" @click="navigate('login')">登录 / 注册</a>
      </span>
      <nav>
        <button :class="{ active: view === 'gallery' }" @click="navigate('gallery')">字库</button>
        <button :class="{ active: view === 'workspace' }" @click="navigate('workspace')">拼字</button>
        <button :class="{ active: view === 'admin' }" @click="navigate('admin')">管理</button>
      </nav>
    </header>
    <main>
      <GalleryView v-if="view === 'gallery'" @open-char="openChar" />
      <PuzzleWorkspace v-else-if="view === 'workspace'" :initial-char="targetChar" />
      <AdminView v-else-if="view === 'admin' && user && user.role === 'admin'" />
      <AuthView v-else-if="view === 'login'" @authed="onAuthed" />
      <div v-else class="no-access">
        <p>管理页面需要管理员账号登录。</p>
        <a href="#/login" @click="navigate('login')">去登录</a>
      </div>
    </main>
  </div>
</template>

<style>
* {
  box-sizing: border-box;
}
body {
  margin: 0;
  font-family: -apple-system, 'Segoe UI', 'Microsoft YaHei', sans-serif;
  background: #f5f6f8;
  color: #222;
}
header {
  background: #fff;
  border-bottom: 1px solid #e0e0e0;
  padding: 12px 20px;
  display: flex;
  align-items: center;
  gap: 16px;
}
header h1 {
  font-size: 18px;
  margin: 0;
}
.conn {
  font-size: 12px;
  border-radius: 10px;
  padding: 2px 10px;
}
.conn.ok {
  background: #e8f5e9;
  color: #2e7d32;
}
.conn.no {
  background: #fdecea;
  color: #c62828;
}
.who {
  font-size: 13px;
  color: #444;
}
.who a {
  color: #2b7de9;
  text-decoration: none;
  margin-left: 6px;
}
nav {
  margin-left: auto;
  display: flex;
  gap: 6px;
}
nav button {
  padding: 6px 16px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background: #fff;
  cursor: pointer;
  font-size: 14px;
}
nav button.active {
  background: #2b7de9;
  color: #fff;
  border-color: #2b7de9;
}
.no-access {
  padding: 60px;
  text-align: center;
  color: #666;
}
.no-access a {
  color: #2b7de9;
}
</style>
