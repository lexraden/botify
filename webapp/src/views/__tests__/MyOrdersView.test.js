import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'

// Обёртка /my-orders тонкая: заголовок, notice после оплаты и список
// (компонент BuyerOrders тестируется отдельно).
const fetchMyOrders = vi.fn()
vi.mock('../../api', () => ({
  fetchMyOrders: (...args) => fetchMyOrders(...args),
  submitOrderReviews: vi.fn(),
  deleteOrderReview: vi.fn(),
}))
const { default: MyOrdersView } = await import('../MyOrdersView.vue')
const { setLocale } = await import('../../services/locale')

describe('MyOrdersView — обёртка списка покупок', () => {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/my-orders', component: MyOrdersView },
    ],
  })

  beforeEach(() => {
    fetchMyOrders.mockReset()
    setLocale('ru') // в jsdom navigator.language = en-US, а тесты про русский UI
    router.push('/my-orders')
  })

  async function mountAt(query) {
    if (query) await router.replace({ query })
    await router.isReady()
    return mount(MyOrdersView, { global: { plugins: [router] } })
  }

  it('показывает заголовок и список покупок', async () => {
    fetchMyOrders.mockResolvedValue([
      { id: 1, status: 'paid', total: '10', currency: 'USDT', items: [] },
    ])
    const wrapper = await mountAt()
    await flushPromises()
    expect(wrapper.text()).toContain('Мои покупки')
    expect(wrapper.text()).toContain('Заказ #1')
  })

  it('notice после создания заказа подсказывает про оплату в @CryptoBot', async () => {
    fetchMyOrders.mockResolvedValue([])
    const wrapper = await mountAt({ created: '42', pay: '1' })
    await flushPromises()
    expect(wrapper.text()).toContain('Заказ #42 создан.')
    expect(wrapper.text()).toContain('@CryptoBot')
  })

  it('без оплаты — честное «оплата временно недоступна»', async () => {
    fetchMyOrders.mockResolvedValue([])
    const wrapper = await mountAt({ created: '7' })
    await flushPromises()
    expect(wrapper.text()).toContain('Заказ #7 создан.')
    expect(wrapper.text()).toContain('Оплата временно недоступна')
  })
})
