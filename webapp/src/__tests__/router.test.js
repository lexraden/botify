import { afterEach, describe, expect, it, vi } from 'vitest'

// Витрина живёт по bot_id из query. Мокаем источник параметра и api, чтобы
// собирать свежий роутер под каждый сценарий (гард entryResolved — состояние
// модуля, сбрасывается вместе с ним).
const fetchMe = vi.fn()
let botId = null
const fullscreen = { enter: vi.fn(), exit: vi.fn() }
vi.mock('../api', () => ({ fetchMe: (...args) => fetchMe(...args) }))
// tg нужен транзитивному i18n (детект языка) — оставляем его пустым
vi.mock('../services/telegram', () => ({
  getBotId: () => botId,
  tg: undefined,
  enterFullscreen: (...args) => fullscreen.enter(...args),
  exitFullscreen: (...args) => fullscreen.exit(...args),
}))

async function buildRouter(startPath) {
  window.history.replaceState({}, '', startPath)
  const { default: router } = await import('../router')
  return router
}

describe('router — bot_id не теряется между переходами', () => {
  afterEach(() => {
    botId = null
    fetchMe.mockReset()
    fullscreen.enter.mockClear()
    fullscreen.exit.mockClear()
    vi.resetModules()
  })

  it('переносит bot_id в цель, где его нет, — Reload Page остаётся в магазине', async () => {
    botId = '5'
    const router = await buildRouter('/')
    await router.push('/product/7')
    expect(router.currentRoute.value.path).toBe('/product/7')
    expect(router.currentRoute.value.query.bot_id).toBe('5')

    // адрес снова с параметром: перезагрузка из Telegram вернёт покупателя
    // на тот же экран, а не в онбординг продавца
    await router.push('/checkout')
    expect(router.currentRoute.value.query.bot_id).toBe('5')
    // продавческий гард не зовёт /me: покупатель опознан по bot_id
    expect(fetchMe).not.toHaveBeenCalled()
  })

  it('явный bot_id цели не перезаписывается', async () => {
    botId = '5'
    const router = await buildRouter('/')
    await router.push({ path: '/', query: { bot_id: '9' } })
    expect(router.currentRoute.value.query.bot_id).toBe('9')
  })

  it('без bot_id адреса продавца ничем не дополняются', async () => {
    const router = await buildRouter('/')
    await router.push('/shops')
    expect(router.currentRoute.value.path).toBe('/shops')
    expect(router.currentRoute.value.query.bot_id).toBeUndefined()
  })
})

describe('router — полный экран только на витрине покупателя', () => {
  afterEach(() => {
    botId = null
    fullscreen.enter.mockClear()
    fullscreen.exit.mockClear()
    vi.resetModules()
  })

  it('покупательские экраны входят в полный экран, кабинет выходит из него', async () => {
    botId = '5'
    const router = await buildRouter('/')
    await router.push('/product/7')
    expect(fullscreen.enter).toHaveBeenCalled()
    expect(fullscreen.exit).not.toHaveBeenCalled()

    // кабинет продавца — обычное окно, системная шапка на месте
    await router.push('/shops')
    expect(fullscreen.exit).toHaveBeenCalled()

    fullscreen.enter.mockClear()
    await router.push('/my-orders')
    expect(fullscreen.enter).toHaveBeenCalled()
  })
})
