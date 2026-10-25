// Обёртка над Telegram WebApp SDK.
// initData отправляется на бэкенд с каждым API-запросом и валидируется там —
// это единственный источник истины о том, кто открыл Mini App и из какого бота.
export const tg = window.Telegram?.WebApp ?? null

// Применение темы (body.tg-dark) переехало в services/theme.js — там же
// выбор покупателя из профиля.
export function initTelegram() {
  if (!tg) return
  tg.ready()
  tg.expand()
  applyContentSafeInset()
}

// Полноэкранный режим и safe-area пришли в Bot API 8.0: на старых клиентах
// методов и полей нет, поэтому каждый вызов проверяет версию сам.
function fullscreenSupported() {
  return (
    tg?.isVersionAtLeast?.('8.0') === true && typeof tg.enterFullscreen === 'function'
  )
}

export function enterFullscreen() {
  if (fullscreenSupported()) tg.enterFullscreen()
}

export function exitFullscreen() {
  if (fullscreenSupported()) tg.exitFullscreen()
}

// Отступ контента от статус-бара в полноэкранном режиме: в обычном окне шапку
// рисует сам клиент и инсет нулевой, в полном экране компенсируем сами.
function applyContentSafeInset() {
  const top = tg?.contentSafeAreaInset?.top ?? 0
  document.body.style.setProperty('--tg-content-top', `${top}px`)
}

export function getInitData() {
  return tg?.initData ?? ''
}

// bot_id прокидывается seller-ботом как query-параметр кнопки Mini App.
// Фиксируем при загрузке: роутер меняет URL, и параметр из адреса пропадает.
const initialBotId = new URLSearchParams(window.location.search).get('bot_id')

export function getBotId() {
  return initialBotId
}

// Кабинет может быть открыт из самого магазина — кнопка «Кабинет магазина» на
// /start seller-бота. Тогда initData подписана токеном этого магазина, а не
// hub-бота, и бэкенду нужен его id заголовком X-Bot-Id (берётся из роута
// /shop/:botId). Владельца бэкенд сверяет сам — заголовок прав не даёт.
let contextBotId = null

export function setContextBotId(id) {
  contextBotId = id ?? null
}

export function getContextBotId() {
  return contextBotId
}

// Переход в другой чат Telegram (@BotFather, @CryptoBot) из Mini App
export function openTelegramLink(url) {
  if (tg?.openTelegramLink) tg.openTelegramLink(url)
  else window.open(url, '_blank')
}

// Закрыть Mini App. false — мы не в Telegram, закрывать нечего: вызывающий
// тогда идёт запасным путём
export function closeApp() {
  if (typeof tg?.close !== 'function') return false
  tg.close()
  return true
}

// Инсет меняется при входе/выходе из полного экрана и повороте устройства
if (typeof tg?.onEvent === 'function') {
  tg.onEvent('contentSafeAreaChanged', applyContentSafeInset)
}
