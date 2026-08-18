// Обёртка над Telegram WebApp SDK.
// initData отправляется на бэкенд с каждым API-запросом и валидируется там —
// это единственный источник истины о том, кто открыл Mini App и из какого бота.
export const tg = window.Telegram?.WebApp ?? null

export function initTelegram() {
  if (!tg) return
  tg.ready()
  tg.expand()
}

export function getInitData() {
  return tg?.initData ?? ''
}

// bot_id прокидывается seller-ботом как query-параметр кнопки Mini App
export function getBotId() {
  return new URLSearchParams(window.location.search).get('bot_id')
}
