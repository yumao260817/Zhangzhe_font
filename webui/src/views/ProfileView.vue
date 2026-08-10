<script setup>
import { ref, onMounted } from 'vue'
import { api, getToken } from '../auth.js'

const props = defineProps({
  user: { type: Object, default: null },
})

const cands = ref([])
const loading = ref(true)

const STATUS_LABEL = { pending: '待审核', approved: '已过审', rejected: '未过审' }
const ROLE_LABEL = { admin: '管理员', reviewer: '审核员', user: '粉丝' }

onMounted(async () => {
  try {
    const res = await api('/api/my/candidates')
    if (res.ok) {
      cands.value = await res.json()
    }
  } catch (e) {
    /* 忽略加载失败 */
  } finally {
    loading.value = false
  }
})

function byStatus(status) {
  return cands.value.filter((c) => c.status === status)
}

function goHome() {
  window.location.hash = '#/gallery'
}
</script>

<template>
  <div class="profile">
    <div class="head">
      <h2>个人主页</h2>
      <button class="primary" @click="goHome">返回首页</button>
    </div>
    <div class="info">
      <p>昵称：{{ user.name || '（未设置）' }}</p>
      <p>邮箱：{{ user.email }}</p>
      <p>角色：{{ ROLE_LABEL[user.role] || '粉丝' }}</p>
    </div>
    <h3>我提交的字</h3>
    <p v-if="loading">加载中…</p>
    <template v-else-if="cands.length">
      <template v-for="(st, key) in { pending: '待审核', approved: '已过审', rejected: '未过审' }" :key="key">
        <h4 v-if="byStatus(key).length" :class="`st-${key}`">{{ st }}（{{ byStatus(key).length }}）</h4>
        <ul v-if="byStatus(key).length" class="cand-list">
          <li v-for="c in byStatus(key)" :key="c.uid">
            <img :src="`/api/candidates/${c.uid}/png?token=${getToken()}`" alt="" />
            <span class="char">{{ c.char }}</span>
            <span :class="`badge st-${c.status}`">{{ STATUS_LABEL[c.status] }}</span>
            <span class="time">{{ c.created_at }}</span>
            <span class="note">{{ c.note || '' }}</span>
          </li>
        </ul>
      </template>
    </template>
    <p v-else>暂无提交记录</p>
  </div>
</template>

<style scoped>
.profile {
  max-width: 720px;
  margin: 0 auto;
  padding: 24px 20px;
}
.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.head h2 {
  margin: 0 0 10px;
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
.info {
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 14px 18px;
  margin-bottom: 20px;
}
.info p {
  margin: 6px 0;
}
h3 {
  font-size: 15px;
}
h4 {
  font-size: 14px;
  margin: 14px 0 8px;
}
.st-pending {
  color: #f9a825;
}
.st-approved {
  color: #2e7d32;
}
.st-rejected {
  color: #c62828;
}
.badge {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 10px;
  color: #fff;
  flex-shrink: 0;
}
.badge.st-pending {
  background: #f9a825;
}
.badge.st-approved {
  background: #2e7d32;
}
.badge.st-rejected {
  background: #c62828;
}
.cand-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.cand-list li {
  display: flex;
  align-items: center;
  gap: 12px;
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 8px 12px;
  margin-bottom: 8px;
}
.cand-list img {
  width: 48px;
  height: 48px;
  object-fit: contain;
  border: 1px solid #eee;
  border-radius: 4px;
  background: #fff;
}
.char {
  font-size: 18px;
  font-family: SimSun, 宋体, serif;
  width: 40px;
}
.time {
  color: #888;
  font-size: 13px;
}
.note {
  color: #666;
  font-size: 13px;
}
</style>
