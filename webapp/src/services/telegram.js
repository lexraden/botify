// Обёртка над Telegram WebApp SDK.
// initData отправляется на бэкенд с каждым API-запросом и валидируется там —
// это единственный источник истины о том, кто открыл Mini App и из какого бота.
export const tg = window.Telegram?.WebApp ?? null

export function initTelegram() {
  if (!tg) return
  tg.ready()
  tg.expand()
  if (tg.colorScheme === 'dark') document.body.classList.add('tg-dark')
  tg.onEvent?.('themeChanged', () => {
    document.body.classList.toggle('tg-dark', tg.colorScheme === 'dark')
  })
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

// Переход в другой чат Telegram (@BotFather, @CryptoBot) из Mini App
export function openTelegramLink(url) {
  if (tg?.openTelegramLink) tg.openTelegramLink(url)
  else window.open(url, '_blank')
}
