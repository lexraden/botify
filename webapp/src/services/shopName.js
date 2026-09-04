import { t } from '../i18n'

// Как назвать магазин в списках кабинета.
//
// У черновика — магазина, заведённого через /newshop до создания бота —
// bot_username равен null. Оба списка магазинов раньше звали
// bot_username.charAt(0) напрямую и падали на такой строке целиком, а роутер
// ведёт в список как раз тогда, когда среди магазинов есть неактивный.
export function shopLabel(bot) {
  return bot.bot_username ? `@${bot.bot_username}` : bot.title || t('shops.noName')
}

export function shopInitial(bot) {
  return shopLabel(bot).replace(/^@/, '').charAt(0).toUpperCase() || '?'
}
