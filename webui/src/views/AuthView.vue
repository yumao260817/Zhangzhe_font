<script setup>
import { ref, watch, onUnmounted } from 'vue'
import { api, getToken, setToken } from '../auth.js'

const emit = defineEmits(['authed'])

const mode = ref('login')
const email = ref('')
const password = ref('')
const name = ref('')
const msg = ref('')
const ok = ref(false)
const busy = ref(false)
const captchaId = ref('')
const captchaQuestion = ref('')
const captchaAnswer = ref('')
const cooldown = ref(0)
let cooldownTimer = null

function startCooldown() {
  cooldown.value = 5
  if (cooldownTimer) clearInterval(cooldownTimer)
  cooldownTimer = setInterval(() => {
    cooldown.value -= 1
    if (cooldown.value <= 0) {
      clearInterval(cooldownTimer)
      cooldownTimer = null
    }
  }, 1000)
}

async function loadCaptcha() {
  if (cooldown.value > 0) return
  captchaId.value = ''
  captchaQuestion.value = ''
  captchaAnswer.value = ''
  try {
    const res = await api('/api/auth/captcha')
    const data = await res.json()
    if (data.captcha_id) {
      captchaId.value = data.captcha_id
      captchaQuestion.value = data.question
      startCooldown()
    }
  } catch (e) {
    /* 验证码不可用时允许注册（后端会兜底拒绝） */
  }
}

onUnmounted(() => {
  if (cooldownTimer) clearInterval(cooldownTimer)
})

async function submit() {
  msg.value = ''
  ok.value = false
  busy.value = true
  try {
    const fd = new FormData()
    fd.append('email', email.value.trim())
    fd.append('password', password.value)
    if (mode.value === 'register') {
      fd.append('name', name.value.trim())
      fd.append('captcha_id', captchaId.value)
      fd.append('captcha_answer', captchaAnswer.value.trim())
    }
    const res = await api(`/api/auth/${mode.value}`, { method: 'POST', body: fd })
    const data = await res.json().catch(() => ({}))
    if (res.ok) {
      msg.value = data.message || '成功'
      ok.value = true
      if (data.token) {
        setToken(data.token)
        emit('authed', data.user)
      } else if (mode.value === 'register') {
        msg.value = '注册成功，请登录'
        ok.value = true
        mode.value = 'login'
        password.value = ''
      }
    } else {
      msg.value = data.detail || '操作失败'
    }
  } catch (e) {
    msg.value = '网络错误'
  } finally {
    busy.value = false
    if (mode.value === 'register') loadCaptcha()
  }
}

watch(mode, (m) => {
  msg.value = ''
  if (m === 'register') loadCaptcha()
})
</script>

<template>
  <div class="auth-wrap">
    <div class="auth-card">
      <h2>{{ mode === 'login' ? '登录' : '注册' }}</h2>
      <form @submit.prevent="submit">
        <label>
          邮箱
          <input v-model="email" type="email" required placeholder="you@example.com" />
        </label>
        <label v-if="mode === 'register'">
          昵称（可选）
          <input v-model="name" type="text" placeholder="如何署名" />
        </label>
        <label>
          密码
          <input v-model="password" type="password" required :minlength="6" placeholder="至少 6 位" />
        </label>
        <label v-if="mode === 'register'">
          验证码
          <div class="caprow">
            <span v-if="captchaQuestion" class="capq">{{ captchaQuestion }}</span>
            <input v-model="captchaAnswer" type="text" required placeholder="计算结果" />
            <button type="button" class="capre" @click="loadCaptcha" :disabled="cooldown > 0">{{ cooldown > 0 ? `（${cooldown}s）` : '换一题' }}</button>
          </div>
        </label>
        <p v-if="msg" :class="ok ? 'ok' : 'err'">{{ msg }}</p>
        <button type="submit" :disabled="busy">{{ busy ? '请稍候…' : mode === 'login' ? '登录' : '注册' }}</button>
      </form>
      <p class="switch">
        {{ mode === 'login' ? '没有账号？' : '已有账号？' }}
        <a href="#" @click.prevent="mode = mode === 'login' ? 'register' : 'login'">
          {{ mode === 'login' ? '去注册' : '去登录' }}
        </a>
      </p>
    </div>
  </div>
</template>

<style scoped>
.auth-wrap {
  display: flex;
  justify-content: center;
  padding: 60px 16px;
}
.auth-card {
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 32px;
  width: 360px;
}
.auth-card h2 {
  margin: 0 0 20px;
  font-size: 20px;
}
label {
  display: block;
  margin-bottom: 14px;
  font-size: 13px;
  color: #555;
}
input {
  display: block;
  width: 100%;
  margin-top: 4px;
  padding: 8px 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-size: 14px;
}
.caprow {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
}
.caprow .capq {
  white-space: nowrap;
  font-size: 15px;
  color: #222;
  min-width: 76px;
}
.caprow input {
  flex: 1;
  margin-top: 0;
}
.capre {
  padding: 8px 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background: #f5f6f8;
  cursor: pointer;
  font-size: 13px;
  white-space: nowrap;
}
button[type='submit'] {
  width: 100%;
  padding: 9px;
  border: none;
  border-radius: 4px;
  background: #2b7de9;
  color: #fff;
  font-size: 15px;
  cursor: pointer;
}
button:disabled {
  opacity: 0.6;
}
.switch {
  margin: 16px 0 0;
  font-size: 13px;
  text-align: center;
}
.switch a {
  color: #2b7de9;
}
p.ok {
  color: #2e7d32;
}
p.err {
  color: #c62828;
}
</style>
