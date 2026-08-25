import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'

const fetchMyOrders = vi.fn()
vi.mock('../../api', () => ({
  fetchMyOrders: (...args) => fetchMyOrders(...args),
  submitOrderReviews: vi.fn(),
  deleteOrderReview: vi.fn(),
}))
const { default: ProfileView } = await import('../ProfileView.vue')
const { locale, setLocale } = await import('../../services/locale')
const { themePref } = await import('../../services/theme')

describe('ProfileView — профиль покупателя', () => {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/profile', component: ProfileView },
    ],
  })

  beforeEach(() => {
    fetchMyOrders.mockReset()
    setLocale('ru')
    themePref.value = null
    router.push('/profile')
  })

  async function mountView() {
    await router.isReady()
    return mount(ProfileView, { global: { plugins: [router] } })
  }

  it('покупки открыты прямо в профиле, отдельного пункта меню нет', async () => {
    fetchMyOrders.mockResolvedValue([
      { id: 1, status: 'paid', total: '10', currency: 'USDT', items: [] },
      { id: 2, status: 'delivered', total: '5', currency: 'USDT', items: [] },
    ])
    const wrapper = await mountView()
    await flushPromises()
    // заказы видны сразу
    expect(wrapper.text()).toContain('Заказ #1')
    expect(wrapper.text()).toContain('Заказ #2')
    // старый пункт меню с счётчиком ушёл
    expect(wrapper.find('.count').exists()).toBe(false)
    // поддержка на месте
    expect(wrapper.text()).toContain('Поддержка')
  })

  it('без ответа API профиль остаётся рабочим, списка просто нет', async () => {
    fetchMyOrders.mockRejectedValue(new Error('offline'))
    const wrapper = await mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('Поддержка')
    expect(wrapper.text()).not.toContain('Заказ #')
  })

  it('кнопки темы и языка переключают состояние', async () => {
    fetchMyOrders.mockResolvedValue([])
    const wrapper = await mountView()
    await flushPromises()

    const prefs = wrapper.findAll('.pref-btn')
    expect(prefs).toHaveLength(2)
    // язык: ru -> en
    await prefs[1].trigger('click')
    expect(locale.value).toBe('en')
    await prefs[1].trigger('click')
    expect(locale.value).toBe('ru')

    // тема: луна = сейчас светло, тап включает тёмную
    expect(prefs[0].text()).toBe('🌙')
    await prefs[0].trigger('click')
    expect(themePref.value).toBe('dark')
    expect(prefs[0].text()).toBe('☀️')
    await prefs[0].trigger('click')
    expect(themePref.value).toBe('light')
    expect(prefs[0].text()).toBe('🌙')
  })
})
