<script setup>
// Модалка «Связаться с нами»: выбор типа обращения (проблема / идея /
// поддержка) и текст. Саму отправку делает родитель через проп submit —
// у покупателя и продавца разные эндпоинты. Контракт: submit возвращает
// Promise; отклонение с Error('feedback.…') показывает этот текст, любая
// другая ошибка — общий feedback.error.
import { computed, onBeforeUnmount, ref } from 'vue'
import { useRouter } from 'vue-router'
import { t } from '../i18n'

const props = defineProps({
  submit: { type: Function, required: true }, // (type, message, screen) => Promise<void>
})
const emit = defineEmits(['close'])

const router = useRouter()

// 'type' -> 'message'; state: idle | sending | sent
const step = ref('type')
const state = ref('idle')
const type = ref('')
const message = ref('')
const error = ref('')

const MAX_LENGTH = 1000
const TYPES = [
  { key: 'bug', icon: '🐛', label: 'feedback.typeBug' },
  { key: 'idea', icon: '💡', label: 'feedback.typeIdea' },
  { key: 'support', icon: '💬', label: 'feedback.typeSupport' },
]

const typeLabel = computed(
  () => TYPES.find((x) => x.key === type.value)?.label ?? 'feedback.title',
)

// экран, с которого написали, — часть контекста обращения на бэкенде
function screen() {
  return router.currentRoute.value.path
}

function choose(key) {
  type.value = key
  step.value = 'message'
}

async function send() {
  if (state.value === 'sending' || !message.value.trim()) return
  state.value = 'sending'
  error.value = ''
  try {
    await props.submit(type.value, message.value.trim(), screen())
    state.value = 'sent'
    closeTimer = setTimeout(() => emit('close'), 1800)
  } catch (e) {
    state.value = 'idle'
    const key = e instanceof Error && e.message.startsWith('feedback.') ? e.message : ''
    error.value = t(key || 'feedback.error')
  }
}

let closeTimer = null
onBeforeUnmount(() => clearTimeout(closeTimer))
</script>

<template>
  <Transition name="fade">
    <div class="overlay" @click.self="emit('close')">
      <div class="sheet" role="dialog" aria-modal="true" :aria-label="t('feedback.title')">
        <header class="head">
          <h3>{{ state === 'sent' ? '' : t(step === 'type' ? 'feedback.title' : typeLabel) }}</h3>
          <button class="close" type="button" aria-label="Закрыть" @click="emit('close')">✕</button>
        </header>

        <!-- успех: держим на экране пару секунд и закрываем сами -->
        <div v-if="state === 'sent'" class="body sent">
          <div class="sent-icon">✅</div>
          <p>{{ t('feedback.thanks') }}</p>
        </div>

        <!-- шаг 1: тип обращения -->
        <div v-else-if="step === 'type'" class="body">
          <p class="notice">{{ t('feedback.subtitle') }}</p>
          <button v-for="x in TYPES" :key="x.key" type="button" class="type-item" @click="choose(x.key)">
            <span class="type-icon">{{ x.icon }}</span>
            <span>{{ t(x.label) }}</span>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--sub)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M9 6l6 6-6 6" />
            </svg>
          </button>
        </div>

        <!-- шаг 2: текст обращения -->
        <div v-else class="body">
          <textarea
            v-model="message"
            class="msg"
            rows="6"
            :maxlength="MAX_LENGTH"
            :placeholder="t('feedback.placeholder')"
          ></textarea>
          <div class="counter">{{ message.length }}/{{ MAX_LENGTH }}</div>
          <p v-if="error" class="error">{{ error }}</p>
          <button
            class="btn send"
            type="button"
            :disabled="state === 'sending' || !message.trim()"
            @click="send"
          >
            {{ t(state === 'sending' ? 'feedback.sending' : 'feedback.send') }}
          </button>
          <button class="back" type="button" @click="step = 'type'">
            ← {{ t('feedback.back') }}
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  z-index: 90; /* ниже глобального лоадера (100) */
  background: color-mix(in srgb, var(--bg) 55%, transparent);
  backdrop-filter: blur(2px);
}
.sheet {
  position: absolute;
  inset: 0; /* во весь экран — как у юридических документов и тарифов */
  display: flex;
  flex-direction: column;
  background: var(--surface);
  animation: slide-up 0.22s ease;
}
.head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
}
.head h3 {
  flex: 1;
  font-size: 15px;
  margin: 0;
}
.close {
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  border: 0;
  border-radius: 11px;
  background: var(--surface2);
  color: var(--text);
  font-size: 14px;
  cursor: pointer;
}
.body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 16px 18px 28px;
  display: flex;
  flex-direction: column;
}
.notice {
  margin: 0 0 14px;
  padding: 10px 12px;
  border-radius: 11px;
  background: var(--surface2);
  font-size: 12.5px;
  line-height: 1.55;
  color: var(--sub);
}
.type-item {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--border);
  background: var(--surface);
  border-radius: 13px;
  padding: 15px 14px;
  margin-bottom: 10px;
  color: var(--text);
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  text-align: left;
}
.type-icon { font-size: 18px; }
.type-item svg { margin-left: auto; }
.msg {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--border);
  border-radius: 13px;
  background: var(--surface);
  color: var(--text);
  padding: 12px 14px;
  font-size: 14px;
  line-height: 1.5;
  resize: none;
}
.counter {
  align-self: flex-end;
  font-size: 11px;
  color: var(--sub);
  margin: 4px 0 10px;
}
.error {
  margin: 0 0 10px;
  font-size: 12.5px;
  color: var(--red, #ff453a);
}
.btn.send {
  height: 46px;
  border: 0;
  border-radius: 13px;
  background: var(--accent);
  color: #fff;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
}
.btn.send:disabled {
  opacity: 0.5;
  cursor: default;
}
.back {
  margin-top: 14px;
  align-self: center;
  border: 0;
  background: none;
  color: var(--sub);
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
}
.sent {
  align-items: center;
  justify-content: center;
  gap: 10px;
}
.sent-icon { font-size: 40px; }
.sent p {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: var(--text);
}
@keyframes slide-up {
  from { transform: translateY(24px); opacity: 0.6; }
  to { transform: translateY(0); opacity: 1; }
}
.fade-enter-active, .fade-leave-active { transition: opacity 0.18s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
