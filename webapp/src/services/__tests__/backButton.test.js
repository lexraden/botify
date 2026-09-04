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
    expect(backTarget('/product/3', null)).toBe('/')
    expect(backTarget('/checkout', null)).toBe('/')
  })

  it('с внутренних экранов с историей — шаг назад', () => {
    expect(backTarget('/product/3', '/')).toBe('BACK')
    expect(backTarget('/profile', '/')).toBe('BACK')
    expect(backTarget('/checkout', '/product/1')).toBe('BACK')
  })

  it('из «Моих покупок» после оплаты — в каталог, а не в пустую корзину', () => {
    expect(backTarget('/my-orders', '/checkout')).toBe('/')
    expect(backTarget('/my-orders', null)).toBe('/')
  })

  it('из «Моих покупок», открытых из профиля, — шаг назад в профиль', () => {
    expect(backTarget('/my-orders', '/profile')).toBe('BACK')
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
    const nav = handlers[0]()
    if (nav) await nav
    expect(router.currentRoute.value.path).toBe('/')
  })

  it('из «Моих покупок» после оплаты клик ведёт в каталог, а не в корзину', async () => {
    // memory-history роутер не пишет в window.history — состояние истории
    // (state.back), которое читает хендлер, симулируем руками
    window.history.replaceState({ back: '/checkout' }, '')
    await router.push('/my-orders')
    handlers[0]()
    await new Promise((r) => setTimeout(r, 0))
    expect(router.currentRoute.value.path).toBe('/')
  })

  it('из «Моих покупок», открытых из профиля, клик возвращает в профиль', async () => {
    await router.push('/profile') // создаём шаг истории в самом роутере
    await router.push('/my-orders')
    window.history.replaceState({ back: '/profile' }, '') // и симулируем window-state
    handlers[0]() // ветка BACK вызывает router.back() без промиса
    await new Promise((r) => setTimeout(r, 0))
    expect(router.currentRoute.value.path).toBe('/profile')
  })
})
