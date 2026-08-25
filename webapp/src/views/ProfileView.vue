<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { t } from '../i18n'
import BrandBadge from '../components/BrandBadge.vue'
import BuyerOrders from '../components/BuyerOrders.vue'
import { locale, setLocale } from '../services/locale'
import { setTheme, themePref } from '../services/theme'
import { openTelegramLink, tg } from '../services/telegram'

const router = useRouter()

// initDataUnsafe используем только чтобы поздороваться: сервер личность из
// него не берёт, авторизация — по подписанному initData на каждом запросе.
const me = tg?.initDataUnsafe?.user ?? null

const SUPPORT_URL = 'https://t.me/Botifyapp_bot'

// тема: явный выбор покупателя, иначе как в клиенте Telegram
const isDark = computed(() =>
  themePref.value ? themePref.value === 'dark' : tg?.colorScheme === 'dark',
)
function toggleTheme() {
  setTheme(isDark.value ? 'light' : 'dark')
}
const toggleLang = () => setLocale(locale.value === 'ru' ? 'en' : 'ru')
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

    <button class="menu-item" @click="openTelegramLink(SUPPORT_URL)">
      <span>{{ t('profile.support') }}</span>
      <span class="muted">{{ t('profile.write') }}</span>
    </button>

    <!-- нижний отступ с запасом под фиксированную плашку «Сделано через Botify» -->
    <BrandBadge />
  </div>
</template>

<style scoped lang="scss">
.profile { padding: 18px 16px 76px; }
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
