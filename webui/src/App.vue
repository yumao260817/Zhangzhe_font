<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import PuzzleWorkspace from './views/PuzzleWorkspace.vue'
import GalleryView from './views/GalleryView.vue'
import AdminView from './views/AdminView.vue'
import AuthView from './views/AuthView.vue'
import ProfileView from './views/ProfileView.vue'
import { api, getToken, setToken } from './auth.js'

const view = ref('gallery')
const targetChar = ref('')
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
  } else if (seg === 'profile') {
    view.value = 'profile'
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
  restoreSession()
  window.addEventListener('hashchange', parseHash)
})
onBeforeUnmount(() => window.removeEventListener('hashchange', parseHash))
</script>

<template>
  <div class="app">
    <header>
      <h1>苟岂开源字体协作平台</h1>
      <span v-if="user" class="who">
        <a href="#/profile" @click.prevent="navigate('profile')">{{ user.name || user.email }}</a>
        <a
          v-if="user.role === 'admin'"
          class="admin-banner"
          href="#/admin"
          @click.prevent="navigate('admin')"
          >后台审核</a
        >
        <a href="#" @click.prevent="logout">退出</a>
      </span>
      <span v-else class="who">
        <a href="#/login" @click="navigate('login')">登录 / 注册</a>
      </span>
    </header>
    <main>
      <GalleryView v-if="view === 'gallery'" @open-char="openChar" />
      <PuzzleWorkspace v-else-if="view === 'workspace'" :initial-char="targetChar" />
      <AdminView v-else-if="view === 'admin' && user && user.role === 'admin'" />
      <AuthView v-else-if="view === 'login'" @authed="onAuthed" />
      <ProfileView v-else-if="view === 'profile' && user" :user="user" />
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
  position: sticky;
  top: 0;
  z-index: 100;
  height: 52px;
  background: #fff;
  border-bottom: 1px solid #e0e0e0;
  padding: 0 20px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 16px;
}
header h1 {
  font-size: 18px;
  margin: 0;
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  white-space: nowrap;
}
.admin-banner {
  display: inline-block;
  padding: 5px 16px;
  background: #2b7de9;
  border-radius: 4px;
  text-decoration: none;
  font-size: 13px;
  font-weight: 600;
}
.who a.admin-banner {
  color: #fff;
}
.who a.admin-banner:hover {
  background: #1f66c4;
}
.who {
  font-size: 13px;
  color: #444;
  display: flex;
  align-items: center;
  gap: 8px;
}
.who a {
  color: #2b7de9;
  text-decoration: none;
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
