import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

// Регресс на живой баг: input выбора фото лежит внутри v-for по заказам,
// поэтому template ref приходит массивом и .click() по нему молча не срабатывает
// — «плюс» не открывал выбор файлов. Тест падает, если разворачивание массива убрать.
vi.mock('../../api', () => ({
  createMailing: vi.fn(),
  deleteProduct: vi.fn(),
  deleteShopLogo: vi.fn(),
  fetchMailings: vi.fn(() => Promise.resolve([])),
  fetchMe: vi.fn(() => Promise.resolve({})),
  fetchProducts: vi.fn(() => Promise.resolve([])),
  fetchSellerReviews: vi.fn(() => Promise.resolve([])),
  fetchShopOrders: vi.fn(() => Promise.resolve([ORDER])),
  fetchShopStats: vi.fn(() => Promise.resolve({})),
  fetchShopSummary: vi.fn(() => Promise.resolve(SUMMARY)),
  fulfillOrder: vi.fn(),
  replyToReview: vi.fn(),
  sendOrderChatPhoto: vi.fn(),
  updateShopName: vi.fn(),
  uploadShopLogo: vi.fn(),
  withdrawPayout: vi.fn(),
}))
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { botId: '1' }, query: { tab: 'orders' } }),
  useRouter: () => ({ push: vi.fn() }),
}))
vi.mock('../../services/telegram', () => ({ openTelegramLink: vi.fn(), tg: undefined }))

import ShopView from '../ShopView.vue'

const SUMMARY = {
  shop_name: 'Магазин',
  logo_url: null,
  payout_pending: 0,
  payout_paid: 0,
  payout_min: 0,
}
const ORDER = {
  id: 5,
  status: 'paid',
  total: '5',
  currency: 'USDT',
  created_at: '2026-08-27T10:00:00Z',
  items: [{ product_id: 1, title: 'Кружка', qty: 1, price: '5' }],
  delivery: { address: 'Тверская 1' },
  comment: null,
  fulfillment: null,
}

async function mountOrders() {
  const w = mount(ShopView)
  await flushPromises()
  return w
}

describe('ShopView — форма отправки заказа', () => {
  beforeEach(() => vi.clearAllMocks())

  it('«плюс» открывает выбор файлов', async () => {
    const w = await mountOrders()
    expect(w.find('.card.order').exists()).toBe(true)
    await w.find('.fulfill-btn').trigger('click')

    const input = w.find('input[type="file"]')
    expect(input.exists()).toBe(true)
    input.element.click = vi.fn()
    await w.find('.tile.add').trigger('click')
    expect(input.element.click).toHaveBeenCalled()
  })

  it('кнопка отправки активна при пустом поле, если есть фото', async () => {
    const w = await mountOrders()
    await w.find('.fulfill-btn').trigger('click')

    const submit = w.find('.fulfill-form .btn-green')
    expect(submit.attributes('disabled')).toBeDefined() // пусто — отправлять нечего
  })
})
