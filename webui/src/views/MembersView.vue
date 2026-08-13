<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../auth.js'

const users = ref([])
const loading = ref(false)
const message = ref('')

const ROLE_LABEL = { admin: '管理员', reviewer: '审核员', user: '粉丝' }

async function loadUsers() {
  loading.value = true
  message.value = ''
  try {
    const res = await api('/api/admin/users')
    if (!res.ok) {
      message.value = (await res.json().catch(() => ({}))).detail || '成员加载失败'
      return
    }
    users.value = await res.json()
  } catch (err) {
    message.value = `成员加载失败: ${err.message}`
  } finally {
    loading.value = false
  }
}

async function setRole(email, role) {
  message.value = ''
  const fd = new FormData()
  fd.append('email', email)
  fd.append('role', role)
  const res = await api('/api/admin/set-role', { method: 'POST', body: fd })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    message.value = body.detail || '操作失败'
    return
  }
  await loadUsers()
}

async function resetPassword(email) {
  if (!window.confirm(`确认重置 ${email} 的密码？其所有登录会话将立即失效。`)) return
  message.value = ''
  const res = await api('/api/admin/reset-password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    message.value = body.detail || '操作失败'
    return
  }
  if (body.temp_password) {
    window.alert(`密码已重置。临时密码：${body.temp_password}\n请线下转交用户，并提醒其登录后尽快修改。`)
  } else {
    message.value = body.message || '若该账户存在，密码已重置'
  }
}

function goHome() {
  window.location.hash = '#/gallery'
}

onMounted(loadUsers)
</script>

<template>
  <div class="members">
    <div class="head">
      <h2>成员管理</h2>
      <button class="primary" @click="goHome">返回首页</button>
    </div>
    <p v-if="message" class="msg">{{ message }}</p>
    <p v-if="loading">加载中…</p>
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
          <td>
            <span class="role-badge" :class="`role-${u.role}`">{{ ROLE_LABEL[u.role] || u.role }}</span>
          </td>
          <td>{{ u.created_at?.slice(0, 10) }}</td>
          <td>
            <button v-if="u.role === 'user'" class="ok" @click="setRole(u.email, 'reviewer')">提升审核员</button>
            <button v-else-if="u.role === 'reviewer'" class="no" @click="setRole(u.email, 'user')">降为粉丝</button>
            <button class="reset" @click="resetPassword(u.email)">重置密码</button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.members {
  padding: 20px;
  max-width: 900px;
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
.msg {
  color: #c62828;
  font-size: 13px;
}
.user-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  overflow: hidden;
}
.user-table th,
.user-table td {
  text-align: left;
  padding: 8px 10px;
  border-bottom: 1px solid #f0f0f0;
}
.user-table th {
  background: #fafafa;
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
button.ok {
  color: #2e7d32;
  border-color: #2e7d32;
  background: #fff;
  cursor: pointer;
  padding: 3px 10px;
  border-radius: 4px;
  font-size: 12px;
}
button.no {
  color: #c62828;
  border-color: #c62828;
  background: #fff;
  cursor: pointer;
  padding: 3px 10px;
  border-radius: 4px;
  font-size: 12px;
}
button.reset {
  color: #b26a00;
  border-color: #b26a00;
  background: #fff;
  cursor: pointer;
  padding: 3px 10px;
  border-radius: 4px;
  font-size: 12px;
  margin-left: 6px;
}
</style>
