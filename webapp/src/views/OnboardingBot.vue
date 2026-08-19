<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { connectBot } from '../api'
import { openTelegramLink } from '../services/telegram'

const router = useRouter()
const token = ref('')
const saving = ref(false)
const error = ref('')

const ERRORS = {
  bad_format: 'Это не похоже на токен. Он выглядит так: 1234567890:AAEhBOweik6ad9r_QXMEN…',
  get_me_failed: 'Telegram не принял этот токен — возможно, он отозван или скопирован с ошибкой.',
  taken_by_other: 'Этот бот уже подключён к платформе другим продавцом.',
  already_yours: 'Этот бот уже подключён к твоему аккаунту.',
}

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
      router.replace(`/shop/${res.bot.id}`)
    } else {
      error.value = ERRORS[res.error] || 'Не удалось подключить бота. Попробуй ещё раз.'
    }
  } catch (e) {
    error.value = e.response?.data?.detail || 'Не удалось подключить бота. Попробуй ещё раз.'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="step" :class="{ 'kb-open': keyboardOpen }">
    <div class="progress">
      <span class="done" />
      <span class="filled" />
    </div>
    <div class="step-label">Шаг 2 из 2</div>

    <h2>Подключи своего бота</h2>
    <p class="lead">Через него покупатели увидят каталог.</p>

    <ol class="steps">
      <li><span class="num">1</span><span>Открой <b>@BotFather</b>, отправь <b>/newbot</b></span></li>
      <li><span class="num">2</span><span>Придумай имя и username бота</span></li>
      <li><span class="num">3</span><span>Скопируй токен и вставь его ниже</span></li>
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
      <span>Токен хранится только в зашифрованном виде</span>
    </div>

    <div class="alert">
      <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="var(--orange)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="9" /><path d="M12 8v4" /><path d="M12 16h.01" />
      </svg>
      <span>
        Уже есть бот? Отключи его от других конструкторов и вставь его токен — новый создавать
        не нужно.
      </span>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <div class="actions">
      <button class="btn btn-soft" @click="openTelegramLink('https://t.me/BotFather')">
        Открыть @BotFather
      </button>
      <button class="btn btn-primary" :disabled="saving || !token.trim()" @click="submit">
        {{ saving ? 'Проверяю…' : 'Подключить бота' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.step { padding: 20px 18px 118px; }
.step.kb-open { padding-bottom: 75vh; }
.progress { display: flex; gap: 6px; }
.progress span { flex: 1; height: 5px; border-radius: 3px; background: var(--surface2); }
.progress .filled { background: var(--accent); }
.progress .done { background: var(--green); }
.step-label { font-size: 13px; font-weight: 700; color: var(--sub); margin-top: 10px; }
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
  position: fixed; left: 0; right: 0; bottom: 0; padding: 14px 18px 24px;
  display: flex; flex-direction: column; gap: 10px; background: var(--bg);
}
</style>
