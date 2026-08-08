<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../auth.js'

const props = defineProps({
  user: { type: Object, default: null },
})

const cands = ref([])
const loading = ref(true)

onMounted(async () => {
  try {
    const res = await api('/api/candidates?status=approved')
    if (res.ok) {
      const list = await res.json()
      cands.value = list.filter((c) => c.author === (props.user && props.user.email))
    }
  } catch (e) {
    /* 忽略加载失败 */
  } finally {
    loading.value = false
  }
})

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
    </div>
    <h3>我提交的候选（已过审）</h3>
    <p v-if="loading">加载中…</p>
    <ul v-else-if="cands.length" class="cand-list">
      <li v-for="c in cands" :key="c.uid">
        <img :src="`/api/candidates/${c.uid}/png`" alt="" />
        <span class="char">{{ c.char }}</span>
        <span class="time">{{ c.created_at }}</span>
        <span class="note">{{ c.note || '' }}</span>
      </li>
    </ul>
    <p v-else>暂无已过审的候选，快去拼字吧</p>
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
