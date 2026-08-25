import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'

// Мок API: первый вызов отдаёт «Ожидает оплаты», второй — «Оплачен».
const fetchMyOrders = vi.fn()
const submitOrderReviews = vi.fn()
vi.mock('../../api', () => ({
  fetchMyOrders: (...args) => fetchMyOrders(...args),
  submitOrderReviews: (...args) => submitOrderReviews(...args),
}))
const { default: MyOrdersView } = await import('../MyOrdersView.vue')

const order = (status) => [
  { id: 1, status, total: '10', currency: 'USDT', items: [{ product_id: 1, title: 'Гайд', qty: 1, price: '10' }] },
]

describe('MyOrdersView — живые статусы', () => {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/my-orders', component: MyOrdersView },
    ],
  })

  beforeEach(() => {
    vi.useFakeTimers()
    fetchMyOrders.mockReset()
    submitOrderReviews.mockReset()
    router.push('/my-orders')
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  async function mountView() {
    await router.isReady()
    return mount(MyOrdersView, { global: { plugins: [router] } })
  }

  it('показывает статус из первой загрузки', async () => {
    fetchMyOrders.mockResolvedValue(order('pending_payment'))
    const wrapper = await mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('⏳ Ожидает оплаты')
    wrapper.unmount()
  })

  it('обновляет статус по таймеру без перезахода', async () => {
    fetchMyOrders
      .mockResolvedValueOnce(order('pending_payment'))
      .mockResolvedValue(order('paid'))
    const wrapper = await mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('⏳ Ожидает оплаты')

    await vi.advanceTimersByTimeAsync(10_000)
    await flushPromises()
    expect(wrapper.text()).toContain('✅ Оплачен')
    expect(fetchMyOrders).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })

  it('после размонтирования опрос прекращается', async () => {
    fetchMyOrders.mockResolvedValue(order('paid'))
    const wrapper = await mountView()
    await flushPromises()
    wrapper.unmount()

    await vi.advanceTimersByTimeAsync(60_000)
    expect(fetchMyOrders).toHaveBeenCalledTimes(1)
  })

  it('ошибка сети при фоновом обновлении не убивает экран', async () => {
    fetchMyOrders
      .mockResolvedValueOnce(order('paid'))
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValue(order('fulfilled'))
    const wrapper = await mountView()
    await flushPromises()

    await vi.advanceTimersByTimeAsync(10_000) // ошибка — данные остаются
    await flushPromises()
    expect(wrapper.text()).toContain('✅ Оплачен')

    await vi.advanceTimersByTimeAsync(10_000) // сеть вернулась
    await flushPromises()
    expect(wrapper.text()).toContain('📦 Отправлен')
    wrapper.unmount()
  })

  it('доставленный заказ можно оценить: звёзды и сабмит уходят на сервер', async () => {
    fetchMyOrders.mockResolvedValue([
      {
        id: 5,
        status: 'delivered',
        total: '15',
        currency: 'USDT',
        items: [
          { product_id: 1, title: 'Гайд', qty: 1, price: '10', reviewed: false },
          { product_id: 2, title: 'Бургер', qty: 1, price: '5', reviewed: true },
        ],
      },
    ])
    submitOrderReviews.mockResolvedValue([])
    const wrapper = await mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('⭐ Оценить покупки')

    await wrapper.find('.rate-btn').trigger('click')
    // форма только по неотзывленным позициям
    expect(wrapper.findAll('.rate-row')).toHaveLength(1)

    // без оценки хотя бы одного товара отправить нельзя
    await wrapper.find('.form-actions button').trigger('click')
    expect(submitOrderReviews).not.toHaveBeenCalled()

    // четвёртая звезда -> рейтинг 4
    const stars = wrapper.findAll('.stars button')
    await stars[3].trigger('click')
    await wrapper.find('.form-actions button').trigger('click')
    await flushPromises()

    expect(submitOrderReviews).toHaveBeenCalledTimes(1)
    expect(submitOrderReviews).toHaveBeenCalledWith(5, [
      { product_id: 1, rating: 4, body: null },
    ])
    wrapper.unmount()
  })

  it('полностью оценённый заказ кнопку оценки не показывает', async () => {
    fetchMyOrders.mockResolvedValue([
      {
        id: 6,
        status: 'delivered',
        total: '10',
        currency: 'USDT',
        items: [{ product_id: 1, title: 'Гайд', qty: 1, price: '10', reviewed: true }],
      },
    ])
    const wrapper = await mountView()
    await flushPromises()
    expect(wrapper.find('.rate-btn').exists()).toBe(false)
    wrapper.unmount()
  })
})
