// Минимальная локаль для блока условий использования. Глобального i18n в
// проекте нет — этот модуль только выбирает язык текстов T&C: из языка
// профиля Telegram, иначе языка браузера; выбор можно переключить вручную.
import { ref } from 'vue'
import { tg } from './telegram'

const KEY = 'botify:locale'
export const LOCALES = ['ru', 'en']

function detect() {
  const raw = tg?.initDataUnsafe?.user?.language_code ?? navigator.language ?? 'ru'
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
