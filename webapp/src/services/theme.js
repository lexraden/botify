// Тема Mini App. Палитра живёт в styles.css на классе body.tg-dark.
// По умолчанию тема следует за клиентом Telegram (colorScheme), но явный
// выбор покупателя в профиле сильнее: он хранится в localStorage и
// переживает смену темы самим клиентом.
import { ref } from 'vue'
import { tg } from './telegram'

const KEY = 'botify_theme'
const PREFS = ['light', 'dark']

function stored() {
  try {
    const saved = localStorage.getItem(KEY)
    return PREFS.includes(saved) ? saved : null
  } catch {
    return null // приватный режим / заблокированное хранилище
  }
}

// null = как в клиенте Telegram, иначе принудительная 'light' | 'dark'
export const themePref = ref(stored())

export function applyTheme() {
  const dark = themePref.value
    ? themePref.value === 'dark'
    : tg?.colorScheme === 'dark'
  document.body.classList.toggle('tg-dark', dark)
}

export function setTheme(pref) {
  themePref.value = PREFS.includes(pref) ? pref : null
  try {
    if (themePref.value === null) localStorage.removeItem(KEY)
    else localStorage.setItem(KEY, themePref.value)
  } catch {
    /* не критично: при следующем открытии тема определится заново */
  }
  applyTheme()
}

export function toggleTheme() {
  // ориентируемся на то, что реально применено к body
  setTheme(document.body.classList.contains('tg-dark') ? 'light' : 'dark')
}

// Смена темы в клиенте Telegram видна только тем, кто не выбирал свою
if (typeof tg?.onEvent === 'function') {
  tg.onEvent('themeChanged', () => {
    if (themePref.value === null) applyTheme()
  })
}
