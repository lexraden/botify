<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { fetchMe, disableShop, enableShop, deleteShop } from '../api'
import { t } from '../i18n'
import { shopInitial, shopLabel } from '../services/shopName'
import { locale, setLocale } from '../services/locale'
import { setTheme, themePref } from '../services/theme'
import { openTelegramLink, tg } from '../services/telegram'

const router = useRouter()
const route = useRoute()

const bots = ref([])
const note = ref('')
const menuBotId = ref(null)
const confirmDeleteId = ref(null)

onMounted(reload)

async function reload() {
  try {
    const me = await fetchMe()
    bots.value = me.bots ?? []
  } catch {
    bots.value = []
  }
}

function toggleMenu(bot) {
  confirmDeleteId.value = null
  menuBotId.value = menuBotId.value === bot.id ? null : bot.id
}

function askDelete(bot) {
  menuBotId.value = null
  confirmDeleteId.value = bot.id
}

async function onToggle(bot) {
  note.value = ''
  const res = bot.is_active ? await disableShop(bot.id) : await enableShop(bot.id)
  menuBotId.value = null
  note.value = res.is_active
    ? t('shops.enabledNote', { n: shopLabel(res) })
    : t('shops.disabledNote', { n: shopLabel(res) })
  await reload()
}

async function onDelete(bot) {
  note.value = ''
  const res = await deleteShop(bot.id)
  confirmDeleteId.value = null
  menuBotId.value = null
  note.value =
    res.status === 'deleted'
      ? t('shops.deletedNote', { n: shopLabel(bot) })
      : t('shops.hasOrdersNote', { n: shopLabel(bot) })
  await reload()
}

function goAddShop() {
  router.push('/onboarding/bot')
}

// карточка магазина ведёт в его кабинет — как раньше из списка магазинов
function goShop(bot) {
  if (confirmDeleteId.value === bot.id) return
  router.push(`/shop/${bot.id}`)
}

// тема: явный выбор продавца, иначе как в клиенте Telegram
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
      <!-- назад ведёт в тот магазин, из которого открылся профиль, а не на
           шаг истории: экран может быть первым после перезагрузки страницы -->
      <a class="back" @click="router.push(`/shop/${route.params.botId}`)">
        ← {{ t('seller.backToShop') }}
      </a>
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
      <div class="avatar letter">
        {{ t('seller.profileIcon') }}
      </div>
      <div>
        <h2>{{ t('seller.profileTitle') }}</h2>
        <span class="muted">{{ t('seller.profileSubtitle') }}</span>
      </div>
    </div>

    <p v-if="note" class="note">{{ note }}</p>

    <!-- список подключенных ботов -->
    <div v-for="bot in bots" :key="bot.id" class="card shop">
      <div class="main" @click="goShop(bot)">
        <div class="avatar">{{ shopInitial(bot) }}</div>
        <div class="info">
          <b>{{ shopLabel(bot) }}</b>
          <span :class="bot.is_draft ? 'off' : bot.is_active ? 'on' : 'off'">
            {{ bot.is_draft ? t('shops.draft') : bot.is_active ? t('shops.works') : t('shops.off') }}
          </span>
        </div>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--sub)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M9 6l6 6-6 6" />
        </svg>
        <button class="menu-btn" @click.stop="toggleMenu(bot)">⋮</button>
      </div>

      <!-- подтверждение удаления раскрывается на месте карточки -->
      <template v-if="confirmDeleteId === bot.id">
        <p class="danger-q">{{ t('shops.deleteQ', { n: shopLabel(bot) }) }}</p>
        <div class="actions">
          <button class="btn danger" @click="onDelete(bot)">{{ t('shops.yesDelete') }}</button>
          <button class="btn btn-soft" @click="confirmDeleteId = null">{{ t('common.cancel') }}</button>
        </div>
      </template>
      <template v-else-if="menuBotId === bot.id">
        <div class="actions">
          <button v-if="!bot.is_draft" class="btn btn-soft" @click="onToggle(bot)">
            {{ bot.is_active ? t('shops.disableBtn') : t('shops.enableBtn') }}
          </button>
          <button class="btn btn-soft" @click="askDelete(bot)">{{ t('shops.deleteBtn') }}</button>
        </div>
      </template>
    </div>

    <p v-if="bots.length === 0" class="empty">{{ t('seller.noShops') }}</p>

    <button class="btn add" @click="goAddShop">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round">
        <path d="M12 5v14" /><path d="M5 12h14" />
      </svg>
      {{ t('shops.add') }}
    </button>
  </div>
</template>

<style scoped lang="scss">
.profile { padding: 18px 16px 24px; }
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
  width: 52px; height: 52px; border-radius: 17px; background: var(--accent); color: #fff;
  display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 22px;
  flex-shrink: 0;
}
.muted { font-size: 13px; color: var(--sub); }
.note {
  font-size: 13px; font-weight: 700; color: var(--accent);
  margin: -8px 0 14px;
}
.shop { display: flex; flex-direction: column; gap: 10px; margin-bottom: 10px; }
.main { display: flex; align-items: center; gap: 14px; cursor: pointer; }
.info { display: flex; flex-direction: column; gap: 2px; flex-grow: 1; }
.info span { font-size: 12px; }
.on { color: var(--green-text); }
.off { color: var(--sub); }
.menu-btn {
  border: 0; background: none; color: var(--sub); cursor: pointer;
  font-size: 18px; font-weight: 800; padding: 6px 4px; line-height: 1;
}
.actions { display: flex; gap: 8px; }
.actions .btn { flex: 1; height: 40px; }
.btn.danger { background: var(--red-soft, rgba(255, 69, 58, 0.15)); color: var(--red, #ff453a); }
.danger-q { font-size: 13px; font-weight: 700; margin: 0; }
.empty { text-align: center; color: var(--sub); margin: 16px 0; }
.add {
  margin-top: 6px; background: var(--accent-soft); color: var(--accent);
}
</style>