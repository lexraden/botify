<script setup>
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { fetchOrderChat, sendOrderChatMessage, sendOrderChatPhoto } from '../api'
import { t, intlLocale } from '../i18n'

const props = defineProps({
  botId: { type: [String, Number], required: true },
  orderId: { type: [String, Number], required: true },
})

const chat = ref(null)
const error = ref('')
const draft = ref('')
const sending = ref(false)
const scroller = ref(null)
const fileInput = ref(null)

async function reload() {
  try {
    chat.value = await fetchOrderChat(props.botId, props.orderId)
    error.value = ''
  } catch (e) {
    error.value = e.response?.data?.detail || t('chat.loadError')
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

function sendErrorText(e) {
  const detail = e.response?.data?.detail
  if (detail === 'chat_locked') return t('chat.errLocked')
  if (detail === 'too_many_messages') return t('chat.errRate')
  if (e.response?.status === 413) return t('chat.errBigPhoto')
  if (e.response?.status === 400) return t('chat.errNotPhoto')
  return t('chat.errGeneric')
}

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
    error.value = sendErrorText(e)
  } finally {
    sending.value = false
  }
}

// фото отправляется сразу после выбора файла; текст из поля ввода уезжает подписью
function pickPhoto() {
  fileInput.value?.click()
}

async function onFileChange(e) {
  const file = e.target.files?.[0]
  e.target.value = ''
  if (!file || sending.value) return
  sending.value = true
  try {
    await sendOrderChatPhoto(props.botId, props.orderId, file, draft.value.trim())
    draft.value = ''
    error.value = ''
    await reload()
  } catch (err) {
    error.value = sendErrorText(err)
  } finally {
    sending.value = false
  }
}

const fmtTime = (iso) =>
  new Date(iso).toLocaleTimeString(intlLocale(), { hour: '2-digit', minute: '2-digit' })
</script>

<template>
  <div class="chat">
    <!-- покупатель не подписан: обе стороны видят только роль отправителя -->
    <div ref="scroller" class="messages">
      <div v-for="m in chat?.messages ?? []" :key="m.id" class="msg" :class="m.sender">
        <div class="bubble" :class="{ 'with-photo': m.image_url }">
          <a v-if="m.image_url" :href="m.image_url" target="_blank" rel="noopener">
            <img class="photo" :src="m.image_url" :alt="t('chat.photoAlt')" />
          </a>
          <span v-if="m.body">{{ m.body }}</span>
        </div>
        <span class="time">{{ fmtTime(m.created_at) }}</span>
      </div>
      <p v-if="chat && !chat.messages.length" class="empty">{{ t('chat.empty') }}</p>
      <p v-if="!chat && !error" class="empty">{{ t('chat.loading') }}</p>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <template v-if="chat">
      <div v-if="!chat.can_send" class="locked">
        {{ t('chat.lockedBanner') }}
      </div>
      <div v-else class="composer">
        <button class="plus" :disabled="sending" :title="t('chat.attachPhoto')" @click="pickPhoto">+</button>
        <input
          ref="fileInput"
          type="file"
          accept="image/*"
          hidden
          @change="onFileChange"
        />
        <input
          v-model="draft"
          :maxlength="1000"
          :placeholder="t('chat.messagePh')"
          @keydown.enter.prevent="send"
        />
        <button class="send" :disabled="sending || !draft.trim()" @click="send">➤</button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.chat {
  display: flex; flex-direction: column; gap: 10px;
  flex: 1; min-height: 0; /* растягиваемся на остаток экрана, композер внизу */
}
.messages {
  display: flex; flex-direction: column; gap: 8px;
  flex: 1; min-height: 0; overflow-y: auto; padding: 4px 2px;
}
.msg { display: flex; flex-direction: column; align-items: flex-start; max-width: 82%; }
.msg.seller { align-self: flex-end; align-items: flex-end; }
.bubble {
  background: var(--surface2); border-radius: 15px; padding: 9px 12px;
  font-size: 14px; line-height: 1.45; white-space: pre-wrap; word-break: break-word;
}
.msg.seller .bubble { background: var(--accent); color: #fff; border-bottom-right-radius: 5px; }
.msg.customer .bubble { border-bottom-left-radius: 5px; }
.bubble.with-photo { padding: 4px 4px 9px; }
.photo {
  display: block; max-width: min(220px, 100%); max-height: 280px;
  border-radius: 11px; margin-bottom: 6px;
}
.bubble.with-photo > span { display: block; padding: 0 8px; }
.time { font-size: 11px; color: var(--sub); margin-top: 3px; }
.empty { text-align: center; color: var(--sub); margin: 24px 0; }
.error { text-align: center; color: var(--red); font-size: 13px; margin: 0; }
.locked {
  background: var(--surface2); color: var(--sub);
  border-radius: 13px; padding: 12px 13px; font-size: 13px; line-height: 1.45;
}
.composer { display: flex; gap: 8px; align-items: stretch; }
.composer input[type='text'], .composer input:not([type]) { flex: 1; }
.plus {
  width: 48px; border: 0; border-radius: 13px; background: var(--surface2);
  color: var(--text); font-size: 20px; cursor: pointer;
}
.plus:disabled { opacity: 0.5; }
.send {
  width: 48px; border: 0; border-radius: 13px; background: var(--accent); color: #fff;
  font-size: 18px; cursor: pointer;
}
.send:disabled { opacity: 0.5; }
</style>
