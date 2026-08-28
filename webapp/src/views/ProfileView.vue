<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { fetchShop } from '../api'
import { t } from '../i18n'
import BrandBadge from '../components/BrandBadge.vue'
import BuyerOrders from '../components/BuyerOrders.vue'
import LegalModal from '../components/LegalModal.vue'
import { PRIVACY } from '../content/privacy'
import { TOS } from '../content/tos'
import { locale, setLocale } from '../services/locale'
import { setTheme, themePref } from '../services/theme'
import { openTelegramLink, tg } from '../services/telegram'

const router = useRouter()

// initDataUnsafe используем только чтобы поздороваться: сервер личность из
// него не берёт, авторизация — по подписанному initData на каждом запросе.
const me = tg?.initDataUnsafe?.user ?? null

// Адрес поддержки приходит с сервера (SUPPORT_URL в окружении). Не задан —
// пункта нет вовсе: раньше он вёл в hub-бот, и покупатель с проблемой по
// заказу оказывался зарегистрирован продавцом и читал рекламу конструктора.
const supportUrl = ref('')
onMounted(async () => {
  try {
    supportUrl.value = (await fetchShop()).support_url || ''
  } catch {
    /* поддержка — не повод ронять профиль */
  }
})

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
        <button class="pref-btn lang" :aria-label="t('profile.langToggle')" @click="toggleLang">
          {{ locale === 'ru' ? 'EN' : 'RU' }}
        </button>
      </div>
    </div>

    <div class="who">
      <img v-if="me?.photo_url" class="avatar" :src="me.photo_url" :alt="me.first_name" />
      <div v-else class="avatar letter">
        {{ (me?.first_name || '?').charAt(0).toUpperCase() }}
      </div>
      <div>
        <h2>{{ me?.first_name || t('profile.fallbackName') }}</h2>
        <span class="muted">{{ t('profile.role') }}</span>
      </div>
    </div>

    <!-- покупки открыты прямо в профиле, отдельного пункта меню больше нет -->
    <BuyerOrders />

    <button v-if="supportUrl" class="menu-item" @click="openTelegramLink(supportUrl)">
      <span>{{ t('profile.support') }}</span>
      <span class="muted">{{ t('profile.write') }}</span>
    </button>

    <!-- плашка прижимается к низу экрана, а не липнет к блоку сверху -->
    <div class="badge-spacer">
      <BrandBadge />
      <!-- юридические документы: EN — «Terms of Service and Privacy Policy»,
           «and» между ними — не кликабельный текст; RU — двумя строками -->
      <nav class="legal-links" :class="{ stack: locale === 'ru' }" aria-label="Legal">
        <button type="button" @click="legalDoc = 'tos'">{{ t('profile.termsOfService') }}</button>
        <span v-if="locale !== 'ru'" aria-hidden="true">{{ t('profile.and') }}</span>
        <button type="button" @click="legalDoc = 'privacy'">{{ t('profile.privacyPolicy') }}</button>
      </nav>
    </div>

    <LegalModal v-if="legalDoc" :docs="legalDoc === 'tos' ? TOS : PRIVACY" @close="legalDoc = null" />
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
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 10px;
  margin-top: 10px;
  button {
    border: 0;
    background: none;
    padding: 0;
    color: var(--sub);
    font-size: 12px;
    cursor: pointer;
  }
  span { color: var(--sub); font-size: 12px; }
  &.stack { flex-direction: column; gap: 4px; }
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
.avatar {
  width: 52px; height: 52px; border-radius: 17px; object-fit: cover; flex-shrink: 0;
  &.letter {
    background: var(--accent); color: #fff; display: flex; align-items: center;
    justify-content: center; font-size: 22px; font-weight: 800;
  }
}
.muted { font-size: 13px; color: var(--sub); }
.menu-item {
  width: 100%; box-sizing: border-box; border: 1px solid var(--border); background: var(--surface);
  border-radius: 13px; padding: 15px 14px; margin-bottom: 10px; color: var(--text);
  display: flex; justify-content: space-between; align-items: center;
  font-size: 15px; font-weight: 700; cursor: pointer;
}
</style>
