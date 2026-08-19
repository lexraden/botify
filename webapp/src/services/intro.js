// Вводный экран показывается один раз: онбординг может начинаться заново
// (продавец ушёл в @CryptoBot и вернулся), но знакомство повторять не нужно.
const KEY = 'botify:intro_seen'

export function isIntroSeen() {
  try {
    return localStorage.getItem(KEY) === '1'
  } catch {
    return false // приватный режим / заблокированное хранилище
  }
}

export function markIntroSeen() {
  try {
    localStorage.setItem(KEY, '1')
  } catch {
    /* не критично: в худшем случае экран покажется ещё раз */
  }
}
