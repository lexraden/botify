// Переход к созданию бота — общий для экрана условий и экрана «Создай магазин».
//
// Кнопку создания бота (KeyboardButtonRequestManagedBot) Mini App показать не
// может, только чат. Раньше мы уводили туда диплинком, и человек мог упереться
// в лишнюю кнопку START. Теперь сервер присылает сообщение с кнопкой сам, а
// приложение закрывается: открыто оно из чата с hub-ботом, туда же и вернёт —
// ровно к ждущей кнопке. Не вышло (сервер не смог, мы не в Telegram) —
// уходим диплинком, как раньше.
import { sendBotPrompt } from '../api'
import { closeApp, openTelegramLink } from './telegram'

export async function goCreateBot(link) {
  try {
    const { sent } = await sendBotPrompt()
    if (sent && closeApp()) return
  } catch {
    /* запасной путь ниже */
  }
  openTelegramLink(link)
}
