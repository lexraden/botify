<script setup>
import { computed, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { connectBot, fetchMe } from '../api'
import { t, tList } from '../i18n'
import { openTelegramLink } from '../services/telegram'

const router = useRouter()
const token = ref('')
const saving = ref(false)
const error = ref('')

// Повторный вход (уже есть хотя бы один бот): показываем упрощённый экран
// «ещё одного бота», без поздравления о создании магазина.
const addingMore = ref(false)
onMounted(async () => {
  try {
    const me = await fetchMe()
    addingMore.value = Boolean(me.cryptobot_connected && me.bots.length)
  } catch {
    /* нет данных — показываем обычный онбординг */
  }
})

// словарь ошибок подключения — computed, чтобы переключение языка
// в кабинете меняло и будущие сообщения об ошибках
const ERRORS = computed(() => ({
  bad_format: t('bot.err.bad_format'),
  get_me_failed: t('bot.err.get_me_failed'),
  taken_by_other: t('bot.err.taken_by_other'),
  already_yours: t('bot.err.already_yours'),
}))

const tokenInput = ref(null)
const keyboardOpen = ref(false)

// Клавиатура перекрывает нижнюю часть экрана: поднимаем поле ввода к верху.
// Дополнительный нижний отступ нужен, чтобы странице было куда прокрутиться.
function onTokenFocus() {
  keyboardOpen.value = true
  setTimeout(() => {
    tokenInput.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, 300)
}

function onTokenBlur() {
  keyboardOpen.value = false
}

async function submit() {
  if (saving.value || !token.value.trim()) return
  saving.value = true
  error.value = ''
  try {
    const res = await connectBot(token.value.trim())
    if (res.ok) {
      if (addingMore.value) {
        router.replace(`/shop/${res.bot.id}`)
      } else {
        const query = new URLSearchParams({
          bot: String(res.bot.id),
          username: res.bot.bot_username || '',
        })
        router.replace(`/onboarding/done?${query}`)
      }
    } else {
      error.value = ERRORS.value[res.error] || t('bot.err.generic')
    }
  } catch (e) {
    error.value = e.response?.data?.detail || t('bot.err.generic')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="step" :class="{ 'kb-open': keyboardOpen }">
    <h2>{{ addingMore ? t('bot.titleMore') : t('bot.titleNew') }}</h2>
    <p class="lead">{{ t('bot.lead') }}</p>

    <!-- строки шагов — наш словарь с <b>-разметкой, поэтому v-html безопасен -->
    <ol class="steps">
      <li v-for="(step, i) in tList('bot.steps')" :key="i">
        <span class="num">{{ i + 1 }}</span><span v-html="step" />
      </li>
    </ol>

    <input
      ref="tokenInput"
      v-model="token"
      class="token"
      placeholder="1234567890:AA…"
      autocapitalize="off"
      autocorrect="off"
      spellcheck="false"
      @focus="onTokenFocus"
      @blur="onTokenBlur"
    />
    <div class="hint">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--sub)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="4" y="10" width="16" height="10" rx="2.5" /><path d="M8 10V7a4 4 0 0 1 8 0v3" />
      </svg>
      <span>{{ t('bot.tokenHint') }}</span>
    </div>

    <div class="alert">
      <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="var(--orange)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="9" /><path d="M12 8v4" /><path d="M12 16h.01" />
      </svg>
      <span>{{ t('bot.alert') }}</span>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <div class="actions">
      <button class="btn btn-soft" @click="openTelegramLink('https://t.me/BotFather')">
        {{ t('bot.openBotfather') }}
      </button>
      <button class="btn btn-primary" :disabled="saving || !token.trim()" @click="submit">
        {{ saving ? t('bot.checking') : t('bot.connect') }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.step { padding: 20px 18px 118px; }
.step.kb-open { padding-bottom: 75vh; }
h2 { font-size: 21px; margin: 18px 0 10px; }
.lead { font-size: 14px; color: var(--sub); line-height: 1.5; margin: 0; }
.alert {
  display: flex; gap: 10px; align-items: flex-start; margin-top: 14px;
  background: var(--orange-soft); border-radius: 14px; padding: 11px 12px;
  font-size: 13px; color: var(--orange-text); line-height: 1.45;
}
.alert svg { flex-shrink: 0; margin-top: 1px; }
.steps { list-style: none; padding: 0; margin: 16px 0 14px; display: flex; flex-direction: column; gap: 11px; }
.steps li { display: flex; gap: 12px; align-items: center; font-size: 14px; line-height: 1.4; }
.num {
  width: 27px; height: 27px; border-radius: 9px; background: var(--surface2);
  display: flex; align-items: center; justify-content: center; font-weight: 800; flex-shrink: 0;
}
.token { font-family: ui-monospace, 'SF Mono', Menlo, monospace; border-color: var(--accent); }
.hint { display: flex; gap: 8px; align-items: center; margin-top: 9px; font-size: 12px; color: var(--sub); }
.error { color: var(--red); }
.actions {
  position: fixed; left: 0; right: 0; bottom: 0; z-index: 20; padding: 14px 18px 24px;
  display: flex; flex-direction: column; gap: 10px; background: var(--bg);
}
</style>
