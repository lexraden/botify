import { describe, expect, it } from 'vitest'

// telegram.js читает window.Telegram при первом импорте модуля, а статические
// импорты поднимаются выше любого кода файла — поэтому стаб ставим до первого
// импорта backButton и берём его динамически.
const handlers = []
const calls = []
window.Telegram = {
  WebApp: {
    BackButton: {
      show: () => calls.push('show'),
      hide: () => calls.push('hide'),
      onClick: (h) => handlers.push(h),
    },
  },
}
const { backTarget, attachBackButton } = await import('../backButton')
const { createRouter, createMemoryHistory } = await import('vue-router')

describe('backTarget — куда ведёт системная «Назад»', () => {
  it('с внутренних экранов без истории — в каталог', () => {
    expect(backTarget('/product/3', false)).toBe('/')
    expect(backTarget('/checkout', false)).toBe('/')
  })

  it('с внутренних экранов с историей — шаг назад', () => {
    expect(backTarget('/product/3', true)).toBe('BACK')
    expect(backTarget('/checkout', true)).toBe('BACK')
  })

  it('из «Моих покупок» — всегда в каталог, даже с историей', () => {
    // после оплаты предыдущий экран истории — пустая корзина
    expect(backTarget('/my-orders', true)).toBe('/')
    expect(backTarget('/my-orders', false)).toBe('/')
  })
})

describe('attachBackButton — показ и реакция на клик', () => {
  const Empty = { template: '<div />' }
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: Empty },
      { path: '/product/:id', component: Empty },
      { path: '/my-orders', component: Empty },
    ],
  })
  attachBackButton(router)

  it('на корне кнопка спрятана, на внутреннем экране показана', async () => {
    await router.push('/product/1')
    expect(calls).toEqual(['show'])
    await router.push('/')
    expect(calls).toEqual(['show', 'hide'])
    await router.push('/product/2')
    expect(calls).toEqual(['show', 'hide', 'show'])
  })

  it('клик по кнопке без внутренней истории уводит в каталог', async () => {
    window.history.replaceState(null, '')
    expect(handlers.length).toBe(1)
    await handlers[0]()
    expect(router.currentRoute.value.path).toBe('/')
  })

  it('из «Моих покупок» клик ведёт в каталог даже при наличии истории', async () => {
    await router.push('/') // создаём историю, чтобы state.back существовал
    await router.push('/my-orders')
    await handlers[0]()
    expect(router.currentRoute.value.path).toBe('/')
  })
})
