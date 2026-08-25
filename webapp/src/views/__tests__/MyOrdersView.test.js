import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'

// Мок API: первый вызов отдаёт «Ожидает оплаты», второй — «Оплачен».
const fetchMyOrders = vi.fn()
const submitOrderReviews = vi.fn()
const deleteOrderReview = vi.fn()
vi.mock('../../api', () => ({
  fetchMyOrders: (...args) => fetchMyOrders(...args),
  submitOrderReviews: (...args) => submitOrderReviews(...args),
  deleteOrderReview: (...args) => deleteOrderReview(...args),
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
    deleteOrderReview.mockReset()
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
          {
            product_id: 2,
            title: 'Бургер',
            qty: 1,
            price: '5',
            reviewed: true,
            my_review: { rating: 3, body: null },
          },
        ],
      },
    ])
    submitOrderReviews.mockResolvedValue([])
    const wrapper = await mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('⭐ Оценить покупки')

    await wrapper.find('.rate-btn').trigger('click')
    // форма по всем позициям заказа, оценённая открыта заполненной
    expect(wrapper.findAll('.rate-row')).toHaveLength(2)
    const prefilledStars = wrapper.findAll('.rate-row')[1].findAll('.stars button.on')
    expect(prefilledStars).toHaveLength(3)

    // без оценки хотя бы одного товара отправить нельзя
    await wrapper.find('.form-actions button').trigger('click')
    expect(wrapper.text()).toContain('Поставь оценку каждому товару.')
    expect(submitOrderReviews).not.toHaveBeenCalled()

    // четвёртая звезда у неотзывленной позиции -> рейтинг 4, остальное уже предзаполнено
    const stars = wrapper.findAll('.stars button')
    await stars[3].trigger('click')
    await wrapper.find('.form-actions button').trigger('click')
    await flushPromises()

    expect(submitOrderReviews).toHaveBeenCalledTimes(1)
    expect(submitOrderReviews).toHaveBeenCalledWith(5, [
      { product_id: 1, rating: 4, body: null },
      { product_id: 2, rating: 3, body: null },
    ])
    wrapper.unmount()
  })

  it('полностью оценённый заказ: кнопка «Изменить отзыв», текст предзаполнен', async () => {
    fetchMyOrders.mockResolvedValue([
      {
        id: 6,
        status: 'delivered',
        total: '10',
        currency: 'USDT',
        items: [
          {
            product_id: 1,
            title: 'Гайд',
            qty: 1,
            price: '10',
            reviewed: true,
            my_review: { rating: 4, body: 'Годнота' },
          },
        ],
      },
    ])
    const wrapper = await mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('✏️ Изменить отзыв')

    await wrapper.find('.rate-btn').trigger('click')
    expect(wrapper.findAll('.stars button.on')).toHaveLength(4)
    expect(wrapper.find('.rate-note').element.value).toBe('Годнота')
    wrapper.unmount()
  })

  it('«Удалить» снимает отзыв позиции и обновляет список', async () => {
    fetchMyOrders.mockResolvedValue([
      {
        id: 6,
        status: 'delivered',
        total: '10',
        currency: 'USDT',
        items: [
          {
            product_id: 1,
            title: 'Гайд',
            qty: 1,
            price: '10',
            reviewed: true,
            my_review: { rating: 2, body: null },
          },
        ],
      },
    ])
    deleteOrderReview.mockResolvedValue({ status: 'deleted' })
    const wrapper = await mountView()
    await flushPromises()

    await wrapper.find('.rate-btn').trigger('click')
    await wrapper.find('.rate-row .del').trigger('click')
    await flushPromises()

    expect(deleteOrderReview).toHaveBeenCalledTimes(1)
    expect(deleteOrderReview).toHaveBeenCalledWith(6, 1)
    // форма закрылась, заказы перезагружены (первая загрузка + refresh)
    expect(wrapper.find('.review-form').exists()).toBe(false)
    expect(fetchMyOrders).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })
})
