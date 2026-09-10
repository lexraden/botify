<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { fetchBuyerMe, fetchShop, sendBuyerFeedback, updateBuyerName } from '../api'
import { t } from '../i18n'
import BrandBadge from '../components/BrandBadge.vue'
import BuyerOrders from '../components/BuyerOrders.vue'
import FeedbackModal from '../components/FeedbackModal.vue'
import LegalModal from '../components/LegalModal.vue'
import NameEditModal from '../components/NameEditModal.vue'
import { PRIVACY } from '../content/privacy'
import { TOS } from '../content/tos'
import { locale, setLocale } from '../services/locale'
import { setTheme, themePref } from '../services/theme'
import { tg } from '../services/telegram'

const router = useRouter()

// initDataUnsafe даёт имя для первой отрисовки, пока запрос к серверу идёт.
// Личность сервер подтверждает подписанным initData на каждом запросе; аватар
// фото не использует вовсе — только буква имени.
const me = tg?.initDataUnsafe?.user ?? null

// Имя с сервера: своё (покупатель мог его поменять в этом окне), иначе
// актуальное из Telegram. initData здесь стартовое значение.
const name = ref(me?.first_name || '')

// Пункт «Связаться с нами» показывается, только если есть кому доставлять
// обращение (ADMIN_TELEGRAM_IDS на бэкенде). Сбой запроса не роняет профиль.
const feedbackEnabled = ref(false)
const showFeedback = ref(false)
const showNameEdit = ref(false)
onMounted(async () => {
  try {
    feedbackEnabled.value = Boolean((await fetchShop()).feedback_enabled)
  } catch {
    /* канал связи — не повод ронять профиль */
  }
  try {
    const meResp = await fetchBuyerMe()
    name.value = meResp.name || me?.first_name || ''
  } catch {
    /* оффлайн — остаётся имя из initData */
  }
})

// Правка имени: ответ /me несёт действующее имя (после сброса — из Telegram).
async function saveName(value) {
  const meResp = await updateBuyerName(value)
  name.value = meResp.name || me?.first_name || ''
}

// Обращение уходит платформе, а не продавцу магазина. Отдельный текст для
// 429: модалка понимает Error('feedback.…') как ключ перевода.
async function submitFeedback(type, message, screen) {
  try {
    await sendBuyerFeedback(type, message, screen)
  } catch (e) {
    throw new Error(e?.response?.status === 429 ? 'feedback.tooMany' : 'feedback.error')
  }
}

// юридические документы платформы: модалка как в онбординге, 'tos' | 'privacy' | null
const legalDoc = ref(null)

// тема: явный выбор покупателя, иначе как в клиенте Telegram
const isDark = computed(() =>
  themePref.value ? themePref.value === 'dark' : tg?.colorScheme === 'dark',
)
function toggleTheme() {
  setTheme(isDark.value ? 'light' : 'dark')
}
// Выбор языка уезжает на сервер заголовком X-Locale на ближайшем запросе, а
// пуши по уже оформленным заказам берут язык из базы. Закрыв приложение сразу
// после переключения, покупатель получал бы их на старом языке — поэтому
// дёргаем один запрос сразу. Сбой не важен: следующий запрос донесёт выбор.
async function toggleLang() {
  setLocale(locale.value === 'ru' ? 'en' : 'ru')
  try {
    await fetchShop()
  } catch {
    /* язык уже переключён в интерфейсе, донесём со следующим запросом */
  }
}
</script>

<template>
  <div class="profile">
    <div class="top">
      <a class="back" @click="router.push('/')">← {{ t('common.toCatalog') }}</a>
      <!-- настройки внешнего вида: тема и язык -->
      <div class="prefs">
        <button class="pref-btn" :aria-label="t('profile.themeToggle')" @click="toggleTheme">
          {{ isDark ? '☀️' : '🌙' }}
        </button>
        <!-- на кнопке текущий язык, а не тот, на который переключит: RU у
             русского интерфейса, EN у английского -->
        <button class="pref-btn lang" :aria-label="t('profile.langToggle')" @click="toggleLang">
          {{ locale.toUpperCase() }}
        </button>
      </div>
    </div>

    <div class="who">
      <!-- аватар всегда буква: фото профиля не разбираем -->
      <div class="avatar letter">{{ (name || '?').charAt(0).toUpperCase() }}</div>
      <div>
        <h2>
          {{ name || t('profile.fallbackName') }}
          <!-- правка имени рядом с именем, не в меню: это персональное -->
          <button
            class="edit-name"
            type="button"
            :aria-label="t('profile.editName')"
            @click="showNameEdit = true"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M17 3a2.83 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z" />
            </svg>
          </button>
        </h2>
        <span class="muted">{{ t('profile.role') }}</span>
      </div>
    </div>

    <!-- покупки открыты прямо в профиле, отдельного пункта меню больше нет -->
    <BuyerOrders />

    <!-- Без заказа писать продавцу некуда (services/chat.py: чат заводится
         у заказа — сразу при оплате переводом, после оплаты в остальных
         случаях). Без этой строки отсутствие кнопки выглядит багом. -->
    <p class="chat-note">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--sub)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M21 11.5a8.4 8.4 0 0 1-9 8.4 9 9 0 0 1-3.6-.7L3 21l1.9-5a8.3 8.3 0 0 1-.9-3.8 8.4 8.4 0 0 1 8.5-8.2 8.4 8.4 0 0 1 8.5 8z" />
      </svg>
      <span>{{ t('profile.chatNote') }}</span>
    </p>

    <!-- «Связаться с нами» — канал платформы: обращение уходит в Botify
         (пушится владельцу), а не продавцу магазина -->
    <button v-if="feedbackEnabled" class="menu-item" @click="showFeedback = true">
      <span>{{ t('profile.contactUs') }}</span>
    </button>

    <!-- плашка прижимается к низу экрана, а не липнет к блоку сверху -->
    <div class="badge-spacer">
      <BrandBadge />
      <!-- юридические документы: одна строка «Условия · Конфиденциальность» /
           «Terms of Service · Privacy Policy», точка-разделитель не кликабельна -->
      <nav class="legal-links" aria-label="Legal">
        <button type="button" @click="legalDoc = 'tos'">{{ t('profile.termsOfService') }}</button>
        <span aria-hidden="true">·</span>
        <button type="button" @click="legalDoc = 'privacy'">{{ t('profile.privacyPolicy') }}</button>
      </nav>
    </div>

    <LegalModal v-if="legalDoc" :docs="legalDoc === 'tos' ? TOS : PRIVACY" @close="legalDoc = null" />
    <FeedbackModal v-if="showFeedback" :submit="submitFeedback" @close="showFeedback = false" />
    <NameEditModal
      v-if="showNameEdit"
      :initial="name"
      :save="saveName"
      @close="showNameEdit = false"
    />
  </div>
</template>

<style scoped lang="scss">
.profile {
  padding: 18px 16px 24px;
  min-height: 100vh;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
}
.badge-spacer { margin-top: auto; }
.legal-links {
  margin-top: 10px;
  text-align: center;
  button {
    border: 0;
    background: none;
    padding: 0;
    color: var(--sub);
    font-size: 12px;
    cursor: pointer;
  }
  /* точка-разделитель между ссылками — с обычным межсловным пробелом */
  span {
    color: var(--sub);
    font-size: 12px;
    margin: 0 4px;
  }
}
.top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.back {
  color: var(--sub);
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
}
.prefs { display: flex; gap: 8px; }
.pref-btn {
  width: 38px; height: 38px; border-radius: 999px; border: 1px solid var(--border);
  background: var(--surface); color: var(--text); cursor: pointer; font-size: 15px;
  display: flex; align-items: center; justify-content: center;
}
.pref-btn.lang { font-size: 12px; font-weight: 800; }
.who {
  display: flex; align-items: center; gap: 12px; margin-bottom: 18px;
  h2 { font-size: 18px; margin: 0; }
}
.edit-name {
  border: 0; background: none; color: var(--sub); cursor: pointer;
  padding: 3px; margin-left: 4px; vertical-align: baseline;
  display: inline-flex; align-items: center;
}
.avatar {
  width: 52px; height: 52px; border-radius: 17px; object-fit: cover; flex-shrink: 0;
  &.letter {
    background: var(--accent); color: #fff; display: flex; align-items: center;
    justify-content: center; font-size: 22px; font-weight: 800;
  }
}
.muted { font-size: 13px; color: var(--sub); }
.chat-note {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  margin: 0 0 14px;
  font-size: 12px;
  line-height: 1.45;
  color: var(--sub);
  svg { flex-shrink: 0; margin-top: 1px; }
}
.menu-item {
  width: 100%; box-sizing: border-box; border: 1px solid var(--border); background: var(--surface);
  border-radius: 13px; padding: 15px 14px; margin-bottom: 10px; color: var(--text);
  display: flex; justify-content: space-between; align-items: center;
  font-size: 15px; font-weight: 700; cursor: pointer;
}
</style>
