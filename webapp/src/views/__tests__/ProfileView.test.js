import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'

const fetchMyOrders = vi.fn()
const fetchShop = vi.fn()
vi.mock('../../api', () => ({
  fetchMyOrders: (...args) => fetchMyOrders(...args),
  fetchShop: (...args) => fetchShop(...args),
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
    fetchShop.mockReset()
    // форма ответа честная: поля шапки витрины, добавленные для trust-строки
    fetchShop.mockResolvedValue({
      support_url: 'https://t.me/botify_support',
      shop_name: '@petshop_bot',
      logo_url: null,
      rating: null,
      sales_count: 0,
    })
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

  it('без настроенной поддержки кнопки нет — лучше никакой, чем не туда', async () => {
    fetchMyOrders.mockResolvedValue([])
    fetchShop.mockResolvedValue({
      support_url: null,
      shop_name: '@petshop_bot',
      logo_url: null,
      rating: null,
      sales_count: 0,
    })
    const w = await mountView()
    await flushPromises()
    expect(w.text()).not.toContain('Поддержка')
  })

  it('настроенная поддержка показывается пунктом меню', async () => {
    fetchMyOrders.mockResolvedValue([])
    const w = await mountView()
    await flushPromises()
    expect(w.text()).toContain('Поддержка')
  })

  it('под плашкой — ссылки на ToS и Privacy: в RU двумя строками, в EN одной', async () => {
    fetchMyOrders.mockResolvedValue([])
    const w = await mountView()
    await flushPromises()

    const nav = w.find('.legal-links')
    const links = nav.findAll('button')
    expect(links.map((b) => b.text())).toEqual([
      'Условия использования',
      'Политика конфиденциальности',
    ])
    // русская версия: две строки друг над другом, разделителя нет
    expect(nav.classes()).toContain('stack')
    expect(nav.find('span').exists()).toBe(false)

    await links[0].trigger('click')
    expect(w.find('[role="dialog"]').exists()).toBe(true)
    expect(w.find('h3').text()).toBe('Условия использования')
    // документ настоящий, не заглушка: кап и арбитраж в тексте
    expect(w.text()).toContain('US$20')
    await w.find('.close').trigger('click')
    expect(w.find('[role="dialog"]').exists()).toBe(false)

    // английская версия: одна строка «Terms of Service and Privacy Policy»,
    // «and» — обычный текст между двумя кликабельными ссылками
    setLocale('en')
    await flushPromises()
    const navEn = w.find('.legal-links')
    expect(navEn.classes()).not.toContain('stack')
    const and = navEn.find('span')
    expect(and.exists()).toBe(true)
    expect(and.text()).toBe('and')
    expect(and.element.tagName).toBe('SPAN') // не кнопка и не ссылка
    expect(navEn.findAll('button').map((b) => b.text())).toEqual([
      'Terms of Service',
      'Privacy Policy',
    ])

    await navEn.findAll('button')[1].trigger('click')
    expect(w.find('h3').text()).toBe('Privacy Policy')
    await w.find('.close').trigger('click')
  })
})
