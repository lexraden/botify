import { afterEach, describe, expect, it, vi } from 'vitest'

// telegram.js читает window.Telegram при первом импорте модуля — как в
// backButton.test.js: стаб ставим до импорта, модуль берём динамически.
function makeTg({ version = '8.0', inset, noVersionMethod = false } = {}) {
  const calls = []
  const tg = {
    ready: () => calls.push('ready'),
    expand: () => calls.push('expand'),
  }
  if (!noVersionMethod) {
    tg.isVersionAtLeast = (v) => parseFloat(version) >= parseFloat(v)
    tg.enterFullscreen = () => calls.push('enter')
    tg.exitFullscreen = () => calls.push('exit')
  }
  if (inset !== undefined) tg.contentSafeAreaInset = { top: inset }
  return { calls, tg }
}

async function load(tg) {
  window.Telegram = { WebApp: tg }
  return import('../telegram')
}

describe('полноэкранный режим (Bot API 8.0)', () => {
  afterEach(() => {
    vi.resetModules()
    window.Telegram = undefined
  })

  it('на клиенте 8.0+ витрина входит и выходит из полного экрана', async () => {
    const { calls, tg } = makeTg({ version: '8.1' })
    const mod = await load(tg)
    mod.enterFullscreen()
    mod.exitFullscreen()
    expect(calls).toEqual(['enter', 'exit'])
  })

  it('на клиенте старше 8.0 вызовы игнорируются без ошибок', async () => {
    const { calls, tg } = makeTg({ version: '7.10' })
    const mod = await load(tg)
    expect(() => mod.enterFullscreen()).not.toThrow()
    mod.enterFullscreen()
    mod.exitFullscreen()
    expect(calls).toEqual([])
  })

  it('без isVersionAtLeast (старый SDK) полный экран просто недоступен', async () => {
    const { calls, tg } = makeTg({ noVersionMethod: true })
    const mod = await load(tg)
    mod.enterFullscreen()
    mod.exitFullscreen()
    expect(calls).toEqual([])
  })

  it('без Telegram-клиента (обычный браузер) ничего не падает', async () => {
    window.Telegram = undefined
    const mod = await import('../telegram')
    expect(() => {
      mod.enterFullscreen()
      mod.exitFullscreen()
    }).not.toThrow()
  })
})

describe('отступ от статус-бара в полном экране', () => {
  afterEach(() => {
    vi.resetModules()
    window.Telegram = undefined
    document.body.style.removeProperty('--tg-content-top')
  })

  it('инсет попадает в CSS-переменную на body', async () => {
    const { tg } = makeTg({ inset: 24 })
    const mod = await load(tg)
    mod.initTelegram()
    expect(document.body.style.getPropertyValue('--tg-content-top')).toBe('24px')
  })

  it('без инсета переменная равна нулю', async () => {
    const { tg } = makeTg({})
    const mod = await load(tg)
    mod.initTelegram()
    expect(document.body.style.getPropertyValue('--tg-content-top')).toBe('0px')
  })

  it('инсет обновляется по событию contentSafeAreaChanged', async () => {
    const { tg } = makeTg({ inset: 10 })
    let handler = null
    tg.onEvent = (name, h) => {
      if (name === 'contentSafeAreaChanged') handler = h
    }
    const mod = await load(tg)
    expect(handler).toBeTypeOf('function')

    tg.contentSafeAreaInset = { top: 33 }
    handler()
    expect(document.body.style.getPropertyValue('--tg-content-top')).toBe('33px')
  })
})
