<script setup>
// Модалка правки имени покупателя. Сам запрос делает родитель через проп
// save — модалка только собирает ввод. Пустое имя — легальный сброс к имени
// из Telegram (бэкенд понимает пустую строку), поэтому кнопка активна всегда.
import { onMounted, ref } from 'vue'
import { t } from '../i18n'

const props = defineProps({
  initial: { type: String, default: '' }, // текущее имя для предзаполнения
  save: { type: Function, required: true }, // (name) => Promise<void>
})
const emit = defineEmits(['close'])

const MAX_LENGTH = 64
const name = ref(props.initial)
const state = ref('idle') // idle | sending
const error = ref('')

const input = ref(null)
onMounted(() => input.value?.focus())

async function send() {
  if (state.value === 'sending') return
  state.value = 'sending'
  error.value = ''
  try {
    await props.save(name.value.trim())
    emit('close')
  } catch {
    state.value = 'idle'
    error.value = t('nameEdit.error')
  }
}
</script>

<template>
  <Transition name="fade">
    <div class="overlay" @click.self="emit('close')">
      <div class="sheet" role="dialog" aria-modal="true" :aria-label="t('nameEdit.title')">
        <header class="head">
          <h3>{{ t('nameEdit.title') }}</h3>
          <button class="close" type="button" aria-label="Закрыть" @click="emit('close')">✕</button>
        </header>

        <div class="body">
          <input
            ref="input"
            v-model="name"
            class="field"
            type="text"
            :maxlength="MAX_LENGTH"
            :placeholder="t('nameEdit.placeholder')"
          />
          <p class="hint">{{ t('nameEdit.hint') }}</p>
          <p v-if="error" class="error">{{ error }}</p>
          <button class="btn send" type="button" :disabled="state === 'sending'" @click="send">
            {{ t(state === 'sending' ? 'nameEdit.sending' : 'nameEdit.save') }}
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
  inset: 0; /* во весь экран — как у фидбека и юридических документов */
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
.field {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--border);
  border-radius: 13px;
  background: var(--surface);
  color: var(--text);
  padding: 13px 14px;
  font-size: 15px;
}
.hint {
  margin: 8px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--sub);
}
.error {
  margin: 10px 0 0;
  font-size: 12.5px;
  color: var(--red, #ff453a);
}
.btn.send {
  margin-top: 14px;
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
@keyframes slide-up {
  from { transform: translateY(24px); opacity: 0.6; }
  to { transform: translateY(0); opacity: 1; }
}
.fade-enter-active, .fade-leave-active { transition: opacity 0.18s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
