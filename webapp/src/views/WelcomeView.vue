<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { acceptTerms } from '../api'
import { markIntroSeen } from '../services/intro'
import { locale } from '../services/locale'
import { TERMS } from '../content/terms'
import TermsModal from '../components/TermsModal.vue'

const router = useRouter()
const accepted = ref(false)
const saving = ref(false)
const error = ref('')
const termsOpen = ref(false)

// Строки блока условий зависят от языка, выбранного в модалке
const copy = computed(() => TERMS[locale.value])

async function start() {
  if (saving.value) return
  saving.value = true
  error.value = ''
  try {
    await acceptTerms()
    markIntroSeen()
    router.replace('/onboarding/payment')
  } catch (e) {
    error.value = e.response?.data?.detail || 'Не удалось сохранить. Попробуй ещё раз.'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="welcome">
    <h1>Твой магазин внутри Telegram</h1>
    <p class="lead">Твой бот, твои клиенты, твои деньги</p>

    <div class="hero">
      <div class="card preview">
        <div class="cover">📕</div>
        <div class="meta">
          <b>Гайд по обжарке</b>
          <span class="muted">digital · придёт в чат</span>
        </div>
        <div class="price">15 USDT</div>
      </div>
      <div class="paid">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">
          <path d="M20 6L9 17l-5-5" />
        </svg>
        Оплачено
      </div>
    </div>

    <div class="chips">
      <span>Без сайта</span>
      <span>Быстрая оплата</span>
      <span>Своя база</span>
    </div>

    <div class="actions">
      <a href="#" class="terms-link" @click.prevent="termsOpen = true">{{ copy.linkLabel }}</a>
      <label class="agree">
        <input v-model="accepted" type="checkbox">
        <span>{{ copy.disclaimer }}</span>
      </label>
      <button class="btn btn-primary" :disabled="!accepted || saving" @click="start">
        Начать
        <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M5 12h14" /><path d="M13 6l6 6-6 6" />
        </svg>
      </button>
      <p v-if="error" class="error">{{ error }}</p>
      <div class="note">2 шага · ~5 минут</div>
    </div>

    <TermsModal v-if="termsOpen" @close="termsOpen = false" />
  </div>
</template>

<style scoped>
.welcome { padding: 22px 20px 130px; }
h1 {
  font-size: 26px; line-height: 1.2; margin: 8px 0 12px;
}
.lead { font-size: 16px; font-weight: 600; color: var(--sub); line-height: 1.45; margin: 0; }
.hero { position: relative; display: flex; justify-content: center; margin-top: 32px; }
.preview {
  width: 200px; display: flex; flex-direction: column; gap: 11px;
  transform: rotate(-4deg); box-shadow: var(--shadow);
}
.cover {
  height: 86px; border-radius: 16px; background: var(--surface2);
  display: flex; align-items: center; justify-content: center; font-size: 48px;
}
.meta { display: flex; flex-direction: column; gap: 3px; }
.meta b { font-size: 14px; }
.meta .muted { font-size: 12px; }
.price {
  background: var(--accent); color: #fff; border-radius: 12px; height: 38px;
  display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 800;
}
.paid {
  position: absolute; right: 14px; top: 4px; transform: rotate(3deg);
  display: flex; align-items: center; gap: 7px;
  background: var(--green-soft); color: var(--green-text); border: 1px solid var(--border);
  border-radius: 14px; padding: 9px 13px; font-size: 13px; font-weight: 800;
}
/* три плашки держим в одну строку даже на узких экранах */
.chips { display: flex; gap: 6px; justify-content: center; flex-wrap: nowrap; margin-top: 34px; }
.chips span {
  background: var(--surface2); border-radius: 20px; padding: 8px 11px;
  font-size: 13px; font-weight: 700; white-space: nowrap;
}
.actions {
  position: fixed; left: 0; right: 0; bottom: 0; padding: 14px 20px 26px;
  display: flex; flex-direction: column; gap: 10px; background: var(--bg);
}
.terms-link {
  align-self: center;
  font-size: 13px;
  font-weight: 700;
}
/* чекбокс согласия; глобальные стили input здесь не подходят — перекрываем */
.agree {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  font-size: 12.5px;
  line-height: 1.45;
  color: var(--sub);
  cursor: pointer;
}
.agree input {
  width: 17px;
  height: 17px;
  margin: 1px 0 0;
  padding: 0;
  border: none;
  border-radius: 5px;
  accent-color: var(--accent);
  cursor: pointer;
  flex-shrink: 0;
}
.error { color: var(--red); font-size: 13px; text-align: center; margin: 0; }
.note { font-size: 13px; font-weight: 600; color: var(--sub); text-align: center; }
</style>
