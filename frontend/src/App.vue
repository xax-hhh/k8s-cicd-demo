<template>
  <div class="container">
    <header><h1>团队留言板</h1><p>记录你的奇思妙想</p></header>
    <div class="panel">
      <form @submit.prevent="submitMessage">
        <input v-model="author" placeholder="你的昵称" required />
        <textarea v-model="content" placeholder="写下你的留言..." required></textarea>
        <button type="submit">发布留言</button>
      </form>
    </div>
    <div class="panel">
      <h2>最新留言</h2>
      <div v-for="msg in messages" :key="msg.id" class="message">
        <div class="meta"><span class="author">{{ msg.author }}</span><span class="time">{{ msg.created_at }}</span></div>
        <p>{{ msg.content }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
const messages = ref([])
const author = ref('')
const content = ref('')

const fetchMessages = async () => {
  const res = await fetch('/api/messages')
  if (res.ok) messages.value = await res.json()
}

const submitMessage = async () => {
  const res = await fetch('/api/messages', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ author: author.value, content: content.value })
  })
  if (res.ok) {
    author.value = ''
    content.value = ''
    fetchMessages()
  }
}
onMounted(fetchMessages)
</script>

<style>
body { background: #eef2f5; font-family: sans-serif; margin: 0; padding: 20px; }
.container { max-width: 600px; margin: 0 auto; }
header { text-align: center; margin-bottom: 20px; }
.panel { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); margin-bottom: 20px; }
form { display: flex; flex-direction: column; gap: 10px; }
input, textarea { padding: 10px; border: 1px solid #ccc; border-radius: 6px; font-family: inherit; }
button { padding: 10px; background: #409eff; color: white; border: none; border-radius: 6px; cursor: pointer; }
button:hover { background: #66b1ff; }
.message { border-bottom: 1px solid #eee; padding: 12px 0; }
.meta { display: flex; justify-content: space-between; font-size: 12px; color: #888; margin-bottom: 5px; }
.author { font-weight: bold; color: #333; }
p { margin: 0; color: #444; }
</style>