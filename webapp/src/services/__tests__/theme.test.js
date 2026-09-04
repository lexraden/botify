import { afterEach, describe, expect, it, vi } from 'vitest'

// theme.js импортирует tg из telegram.js, который читает window.Telegram при
// первом импорте — стаб до импорта, модуль динамически.
const calls = []
window.Telegram = {
  WebApp: {
    colorScheme: 'light',
    setHeaderColor: (c) => calls.push(['header', c]),
    setBackgroundColor: (c) => calls.push(['bg', c]),
  },
}
const { applyTheme, setTheme } = await import('../theme')

describe('applyTheme — цвет шапки и фона клиента', () => {
  afterEach(() => {
    setTheme(null) // и localStorage, и принудительной темы
    calls.length = 0
  })

  it('светлая палитра витрины уходит в setHeaderColor/setBackgroundColor', () => {
    applyTheme()
    expect(calls).toEqual([
      ['header', '#f6f7f9'],
      ['bg', '#f6f7f9'],
    ])
  })

  it('тёмная палитра следует за явным выбором покупателя', () => {
    setTheme('dark')
    expect(calls).toEqual([
      ['header', '#0e0f13'],
      ['bg', '#0e0f13'],
    ])
    expect(document.body.classList.contains('tg-dark')).toBe(true)
  })

  it('клиент без setHeaderColor (старый SDK) тему не ломает', async () => {
    vi.resetModules()
    window.Telegram = { WebApp: { colorScheme: 'dark' } }
    const { applyTheme: apply } = await import('../theme')
    expect(() => apply()).not.toThrow()
    expect(document.body.classList.contains('tg-dark')).toBe(true)
  })
})
