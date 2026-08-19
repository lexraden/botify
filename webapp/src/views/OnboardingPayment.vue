<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { confirmPayment } from '../api'
import { openTelegramLink } from '../services/telegram'

const router = useRouter()
const saving = ref(false)
const error = ref('')

async function done() {
  if (saving.value) return
  saving.value = true
  error.value = ''
  try {
    await confirmPayment()
    router.replace('/onboarding/bot')
  } catch (e) {
    error.value = e.response?.data?.detail || 'Не удалось сохранить. Попробуй ещё раз.'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="step">
    <div class="progress">
      <span class="filled" />
      <span />
    </div>
    <div class="step-label">Шаг 1 из 2</div>

    <div class="icon">
      <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <rect x="2.5" y="6" width="19" height="13" rx="3" />
        <path d="M16.5 6V5a2 2 0 0 0-2-2h-9a2 2 0 0 0-2 2v1" />
        <circle cx="17" cy="12.5" r="1.4" fill="var(--accent)" stroke="none" />
      </svg>
    </div>

    <h2>Куда придут деньги</h2>
    <p class="lead">
      Выплаты падают на твой баланс в @CryptoBot — выводи оттуда на любой кошелёк.
    </p>

    <ol class="steps">
      <li><span class="num">1</span><span>Открой <b>@CryptoBot</b> по кнопке ниже</span></li>
      <li><span class="num">2</span><span>Нажми <b>/start</b> — этого достаточно</span></li>
      <li><span class="num">3</span><span>Вернись сюда и нажми «Готово»</span></li>
    </ol>

    <p v-if="error" class="error">{{ error }}</p>

    <div class="actions">
      <button class="btn btn-primary" @click="openTelegramLink('https://t.me/CryptoBot')">
        Открыть @CryptoBot
      </button>
      <button class="btn btn-soft" :disabled="saving" @click="done">
        {{ saving ? '…' : 'Готово, я нажал /start' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.step { padding: 20px 18px 110px; }
.progress { display: flex; gap: 6px; }
.progress span { flex: 1; height: 5px; border-radius: 3px; background: var(--surface2); }
.progress .filled { background: var(--accent); }
.step-label { font-size: 13px; font-weight: 700; color: var(--sub); margin-top: 10px; }
.icon {
  width: 62px; height: 62px; border-radius: 20px; background: var(--accent-soft);
  display: flex; align-items: center; justify-content: center; margin: 18px 0 12px;
}
h2 { font-size: 21px; margin: 0 0 10px; }
.lead { font-size: 14px; color: var(--sub); line-height: 1.5; margin: 0; }
.steps { list-style: none; padding: 0; margin: 20px 0 0; display: flex; flex-direction: column; gap: 12px; }
.steps li { display: flex; gap: 12px; align-items: center; font-size: 14px; line-height: 1.4; }
.num {
  width: 27px; height: 27px; border-radius: 9px; background: var(--surface2);
  display: flex; align-items: center; justify-content: center; font-weight: 800; flex-shrink: 0;
}
.error { color: var(--red); }
.actions {
  position: fixed; left: 0; right: 0; bottom: 0; padding: 14px 18px 24px;
  display: flex; flex-direction: column; gap: 10px; background: var(--bg);
}
</style>
