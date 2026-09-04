import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// locale — модульное состояние (ref на экспорте), а Telegram читается при
// первом импорте модуля: пересобираем модуль под каждый сценарий.
const state = vi.hoisted(() => ({ tg: undefined }))
// геттер: фабрика мока кешируется навсегда (resetModules её не перезапускает),
// а читать актуальный state.tg нужно при каждой пересборке locale
vi.mock('../../services/telegram', () => ({
  get tg() {
    return state.tg
  },
}))

async function loadLocale() {
  vi.resetModules()
  return import('../locale')
}

describe('locale — язык определяет Telegram', () => {
  beforeEach(() => localStorage.clear())
  afterEach(() => {
    state.tg = undefined
  })

  it('русский language_code даёт ru', async () => {
    state.tg = { initDataUnsafe: { user: { language_code: 'ru' } } }
    expect((await loadLocale()).locale.value).toBe('ru')
  })

  it('другие языки и пустые данные — английский по умолчанию', async () => {
    state.tg = { initDataUnsafe: { user: { language_code: 'uk' } } }
    expect((await loadLocale()).locale.value).toBe('en')

    state.tg = { initDataUnsafe: { user: { language_code: 'en' } } }
    expect((await loadLocale()).locale.value).toBe('en')

    state.tg = { initDataUnsafe: {} } // пользователь без языка
    expect((await loadLocale()).locale.value).toBe('en')

    state.tg = undefined // Telegram не передал ничего
    expect((await loadLocale()).locale.value).toBe('en')
  })

  it('ручной выбор из хранилища главнее детекта', async () => {
    state.tg = { initDataUnsafe: { user: { language_code: 'ru' } } }
    localStorage.setItem('botify:locale', 'en')
    expect((await loadLocale()).locale.value).toBe('en')

    localStorage.setItem('botify:locale', 'ru')
    state.tg = { initDataUnsafe: { user: { language_code: 'en' } } }
    expect((await loadLocale()).locale.value).toBe('ru')
  })
})
