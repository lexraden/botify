import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'

// Мок API: первый вызов отдаёт «Ожидает оплаты», второй — «Оплачен».
const fetchMyOrders = vi.fn()
vi.mock('../../api', () => ({
  fetchMyOrders: (...args) => fetchMyOrders(...args),
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
})
