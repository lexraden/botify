// Единый источник локали всего Mini App (i18n.js читает отсюда же): начальный
// язык берём из Telegram-профиля пользователя, дальше выбор живёт вручную.
import { ref } from 'vue'
import { tg } from './telegram'

const KEY = 'botify:locale'
export const LOCALES = ['ru', 'en']

function detect() {
  // русский, только если так настроен сам Telegram; нет данных или другой
  // язык — английский всегда (решение владельца: дефолт платформы EN)
  const raw = tg?.initDataUnsafe?.user?.language_code ?? ''
  return String(raw).toLowerCase().startsWith('ru') ? 'ru' : 'en'
}

function stored() {
  try {
    const saved = localStorage.getItem(KEY)
    return LOCALES.includes(saved) ? saved : null
  } catch {
    return null // приватный режим / заблокированное хранилище
  }
}

export const locale = ref(stored() ?? detect())

export function setLocale(value) {
  if (!LOCALES.includes(value)) return
  locale.value = value
  try {
    localStorage.setItem(KEY, value)
  } catch {
    /* не критично: при следующем открытии язык определится заново */
  }
}
