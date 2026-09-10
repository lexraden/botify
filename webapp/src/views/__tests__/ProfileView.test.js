import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'

const fetchMyOrders = vi.fn()
const fetchShop = vi.fn()
const sendBuyerFeedback = vi.fn()
const fetchBuyerMe = vi.fn()
const updateBuyerName = vi.fn()
vi.mock('../../api', () => ({
  fetchMyOrders: (...args) => fetchMyOrders(...args),
  fetchShop: (...args) => fetchShop(...args),
  sendBuyerFeedback: (...args) => sendBuyerFeedback(...args),
  fetchBuyerMe: (...args) => fetchBuyerMe(...args),
  updateBuyerName: (...args) => updateBuyerName(...args),
  submitOrderReviews: vi.fn(),
  deleteOrderReview: vi.fn(),
}))
// initDataUnsafe даёт стартовое имя для отрисовки; фото профиля приложение
// не использует вовсе — тест следит, чтобы аватар оставался буквой
vi.mock('../../services/telegram', () => ({
  tg: {
    colorScheme: 'light',
    initDataUnsafe: { user: { first_name: 'Телегеша', photo_url: 'https://t.me/pic.jpg' } },
  },
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
    sendBuyerFeedback.mockReset()
    fetchBuyerMe.mockReset()
    updateBuyerName.mockReset()
    // по умолчанию своего имени нет: показывается Telegram-имя
    fetchBuyerMe.mockResolvedValue({ name: null, telegram_name: null })
    // форма ответа честная: поля шапки витрины, добавленные для trust-строки
    fetchShop.mockResolvedValue({
      feedback_enabled: true,
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
    // канал связи с платформой на месте
    expect(wrapper.text()).toContain('Связаться с нами')
  })

  it('без ответа API профиль остаётся рабочим, списка просто нет', async () => {
    fetchMyOrders.mockRejectedValue(new Error('offline'))
    const wrapper = await mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('Связаться с нами')
    expect(wrapper.text()).not.toContain('Заказ #')
  })

  it('кнопки темы и языка переключают состояние', async () => {
    fetchMyOrders.mockResolvedValue([])
    const wrapper = await mountView()
    await flushPromises()

    const prefs = wrapper.findAll('.pref-btn')
    expect(prefs).toHaveLength(2)
    // На кнопке — текущий язык, а не тот, на который она переключит: при
    // русском интерфейсе там RU. Раньше было наоборот и читалось как «сейчас
    // английский».
    expect(locale.value).toBe('ru')
    expect(prefs[1].text()).toBe('RU')

    await prefs[1].trigger('click')
    expect(locale.value).toBe('en')
    expect(prefs[1].text()).toBe('EN')

    await prefs[1].trigger('click')
    expect(locale.value).toBe('ru')
    expect(prefs[1].text()).toBe('RU')

    // тема: луна = сейчас светло, тап включает тёмную
    expect(prefs[0].text()).toBe('🌙')
    await prefs[0].trigger('click')
    expect(themePref.value).toBe('dark')
    expect(prefs[0].text()).toBe('☀️')
    await prefs[0].trigger('click')
    expect(themePref.value).toBe('light')
    expect(prefs[0].text()).toBe('🌙')
  })

  it('в профиле сказано, что чат с продавцом открывается только после оплаты', async () => {
    fetchMyOrders.mockResolvedValue([])
    const w = await mountView()
    await flushPromises()

    const note = w.find('.chat-note')
    expect(note.exists()).toBe(true)
    expect(note.text()).toContain('после оплаты')

    setLocale('en')
    await w.vm.$nextTick()
    expect(w.find('.chat-note').text()).toContain('after payment')
  })

  it('без настроенной доставки фидбека пункта нет — лучше никакой, чем не туда', async () => {
    fetchMyOrders.mockResolvedValue([])
    fetchShop.mockResolvedValue({
      feedback_enabled: false,
      shop_name: '@petshop_bot',
      logo_url: null,
      rating: null,
      sales_count: 0,
    })
    const w = await mountView()
    await flushPromises()
    expect(w.text()).not.toContain('Связаться с нами')
  })

  it('пункт открывает модалку, обращение уходит платформе с экраном', async () => {
    fetchMyOrders.mockResolvedValue([])
    sendBuyerFeedback.mockResolvedValue({ status: 'sent' })
    const w = await mountView()
    await flushPromises()

    await w.findAll('.menu-item')[0].trigger('click')
    const dialog = w.find('[role="dialog"]')
    expect(dialog.exists()).toBe(true)
    // три типа обращения
    expect(dialog.text()).toContain('Сообщить о проблеме')
    expect(dialog.text()).toContain('Предложить идею')
    expect(dialog.text()).toContain('Написать в поддержку')

    await dialog.findAll('.type-item')[0].trigger('click')
    await dialog.find('textarea').setValue('Сломалась корзина')
    await dialog.find('.btn.send').trigger('click')
    await flushPromises()

    expect(sendBuyerFeedback).toHaveBeenCalledWith('bug', 'Сломалась корзина', '/profile')
    expect(dialog.text()).toContain('Сообщение отправлено')
  })

  it('имя приходит с сервера и замещает стартовое из initData', async () => {
    fetchMyOrders.mockResolvedValue([])
    fetchBuyerMe.mockResolvedValue({ name: 'Алиса', telegram_name: 'Телегеша' })
    const w = await mountView()
    await flushPromises()

    expect(w.find('h2').text()).toContain('Алиса')
    // буква аватара — от действующего имени
    expect(w.find('.avatar.letter').text()).toBe('А')
  })

  it('аватар всегда буква: фото профиля не разбираем', async () => {
    fetchMyOrders.mockResolvedValue([])
    const w = await mountView()
    await flushPromises()

    expect(w.find('img.avatar').exists()).toBe(false)
    expect(w.find('.avatar.letter').exists()).toBe(true)
  })

  it('карандаш открывает правку, сохранение переименовывает и закрывает', async () => {
    fetchMyOrders.mockResolvedValue([])
    updateBuyerName.mockResolvedValue({ name: 'Маша', telegram_name: 'Телегеша' })
    const w = await mountView()
    await flushPromises()

    await w.find('.edit-name').trigger('click')
    const dialog = w.find('[role="dialog"]')
    expect(dialog.exists()).toBe(true)
    expect(dialog.find('input').element.value).toBe('Телегеша')

    await dialog.find('input').setValue('Маша')
    await dialog.find('.btn.send').trigger('click')
    await flushPromises()

    expect(updateBuyerName).toHaveBeenCalledWith('Маша')
    // шапка показала новое имя, модалка закрылась
    expect(w.find('h2').text()).toContain('Маша')
    expect(w.find('[role="dialog"]').exists()).toBe(false)
  })

  it('под плашкой — ссылки на ToS и Privacy: одна строка с точкой, в RU и EN', async () => {
    fetchMyOrders.mockResolvedValue([])
    const w = await mountView()
    await flushPromises()

    const nav = w.find('.legal-links')
    const links = nav.findAll('button')
    expect(links.map((b) => b.text())).toEqual(['Условия', 'Конфиденциальность'])
    // разделитель-точка — обычный текст между двумя кликабельными ссылками
    const dot = nav.find('span')
    expect(dot.exists()).toBe(true)
    expect(dot.text()).toBe('·')
    expect(dot.element.tagName).toBe('SPAN') // не кнопка и не ссылка

    await links[0].trigger('click')
    expect(w.find('[role="dialog"]').exists()).toBe(true)
    expect(w.find('h3').text()).toBe('Условия использования')
    // документ настоящий, не заглушка: кап и арбитраж в тексте
    expect(w.text()).toContain('US$20')
    await w.find('.close').trigger('click')
    expect(w.find('[role="dialog"]').exists()).toBe(false)

    setLocale('en')
    await flushPromises()
    const navEn = w.find('.legal-links')
    expect(navEn.find('span').text()).toBe('·')
    expect(navEn.findAll('button').map((b) => b.text())).toEqual([
      'Terms of Service',
      'Privacy Policy',
    ])

    await navEn.findAll('button')[1].trigger('click')
    expect(w.find('h3').text()).toBe('Privacy Policy')
    await w.find('.close').trigger('click')
  })
})
