<script setup>
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { fetchOrderChat, sendOrderChatMessage } from '../api'

const props = defineProps({
  botId: { type: [String, Number], required: true },
  orderId: { type: [String, Number], required: true },
})

const chat = ref(null)
const error = ref('')
const draft = ref('')
const sending = ref(false)
const scroller = ref(null)

async function reload() {
  try {
    chat.value = await fetchOrderChat(props.botId, props.orderId)
    error.value = ''
  } catch (e) {
    error.value = e.response?.data?.detail || 'Не удалось загрузить чат'
  }
}

// опрос, пока экран открыт; в свёрнутом Telegram поллинг не нужен
let pollTimer = null
function pollIfVisible() {
  if (document.visibilityState === 'visible') reload()
}
onMounted(() => {
  reload()
  pollTimer = setInterval(pollIfVisible, 4000)
})
onUnmounted(() => clearInterval(pollTimer))

// новое сообщение — прокручиваем вниз (первая загрузка и поллинг одинаково)
watch(
  () => chat.value?.messages.length,
  async () => {
    await nextTick()
    const el = scroller.value
    if (el) el.scrollTop = el.scrollHeight
  },
)

async function send() {
  const body = draft.value.trim()
  if (!body || sending.value) return
  sending.value = true
  try {
    await sendOrderChatMessage(props.botId, props.orderId, body)
    draft.value = ''
    error.value = ''
    await reload()
  } catch (e) {
    const detail = e.response?.data?.detail
    error.value =
      detail === 'chat_locked'
        ? 'Чат уже закрыт для новых сообщений.'
        : detail === 'too_many_messages'
          ? 'Слишком много сообщений подряд — подожди немного.'
          : 'Не получилось отправить — попробуй ещё раз.'
  } finally {
    sending.value = false
  }
}

const fmtTime = (iso) =>
  new Date(iso).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
</script>

<template>
  <div class="chat">
    <!-- покупатель не подписан: обе стороны видят только роль отправителя -->
    <div ref="scroller" class="messages">
      <div v-for="m in chat?.messages ?? []" :key="m.id" class="msg" :class="m.sender">
        <div class="bubble">{{ m.body }}</div>
        <span class="time">{{ fmtTime(m.created_at) }}</span>
      </div>
      <p v-if="chat && !chat.messages.length" class="empty">Сообщений пока нет.</p>
      <p v-if="!chat && !error" class="empty">Загружаем…</p>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <template v-if="chat">
      <div v-if="!chat.can_send" class="locked">
        Этот чат закрыт для новых сообщений — окно для обсуждения заказа истекло.
      </div>
      <div v-else class="composer">
        <input
          v-model="draft"
          :maxlength="1000"
          placeholder="Сообщение…"
          @keydown.enter.prevent="send"
        />
        <button class="send" :disabled="sending || !draft.trim()" @click="send">➤</button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.chat { display: flex; flex-direction: column; gap: 10px; }
.messages {
  display: flex; flex-direction: column; gap: 8px;
  max-height: 60vh; overflow-y: auto; padding: 4px 2px;
}
.msg { display: flex; flex-direction: column; align-items: flex-start; max-width: 82%; }
.msg.seller { align-self: flex-end; align-items: flex-end; }
.bubble {
  background: var(--surface2); border-radius: 15px; padding: 9px 12px;
  font-size: 14px; line-height: 1.45; white-space: pre-wrap; word-break: break-word;
}
.msg.seller .bubble { background: var(--accent); color: #fff; border-bottom-right-radius: 5px; }
.msg.customer .bubble { border-bottom-left-radius: 5px; }
.time { font-size: 11px; color: var(--sub); margin-top: 3px; }
.empty { text-align: center; color: var(--sub); margin: 24px 0; }
.error { text-align: center; color: var(--red); font-size: 13px; margin: 0; }
.locked {
  background: var(--surface2); color: var(--sub);
  border-radius: 13px; padding: 12px 13px; font-size: 13px; line-height: 1.45;
}
.composer { display: flex; gap: 8px; align-items: stretch; }
.composer input { flex: 1; }
.send {
  width: 48px; border: 0; border-radius: 13px; background: var(--accent); color: #fff;
  font-size: 18px; cursor: pointer;
}
.send:disabled { opacity: 0.5; }
</style>
