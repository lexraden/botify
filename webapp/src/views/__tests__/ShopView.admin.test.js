import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

vi.mock('../../api', () => ({
  approveReview: vi.fn(),
  deleteProduct: vi.fn(),
  deleteShopLogo: vi.fn(),
  fetchMe: vi.fn(() => Promise.resolve({})),
  fetchProducts: vi.fn(() => Promise.resolve([])),
  fetchSellerReviews: vi.fn(() => Promise.resolve([])),
  fetchShopOrders: vi.fn(() => Promise.resolve([])),
  fetchShopStats: vi.fn(() => Promise.resolve({})),
  fetchShopSummary: vi.fn(() => Promise.resolve(SUMMARY)),
  fulfillOrder: vi.fn(),
  rejectReview: vi.fn(),
  replyToReview: vi.fn(),
  sendOrderChatPhoto: vi.fn(),
  updateShopName: vi.fn(),
  uploadShopLogo: vi.fn(),
  withdrawPayout: vi.fn(),
}))
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { botId: '1' }, query: {} }),
  useRouter: () => ({ push: vi.fn() }),
}))
vi.mock('../../services/telegram', () => ({ openTelegramLink: vi.fn(), tg: undefined }))

import ShopView from '../ShopView.vue'
import { fetchShopSummary } from '../../api'

const SUMMARY = {
  shop_name: 'Магазин',
  logo_url: null,
  payout_pending: 12.5,
  payout_paid: 3,
  payout_min: 10,
  limits: {},
}

async function mountStats() {
  const w = mount(ShopView)
  await flushPromises()
  // вкладка «Статистика» — четвёртая в навигации; там живут кошелёк и тариф
  await w.findAll('nav button')[3].trigger('click')
  return w
}

describe('ShopView — кабинет для админа магазина', () => {
  beforeEach(() => vi.clearAllMocks())

  it('владельцу виден кошелёк и баланс кассы', async () => {
    const w = await mountStats()
    expect(w.find('.card.wallet').exists()).toBe(true)
    // зелёная карточка баланса в верхней строке
    expect(w.find('.stats .card.green').exists()).toBe(true)
  })

  it('админу кошелёк и баланс не показываются — деньги не его зона', async () => {
    fetchShopSummary.mockResolvedValue({ ...SUMMARY, viewer_role: 'admin' })
    const w = await mountStats()
    expect(w.find('.card.wallet').exists()).toBe(false)
    expect(w.find('.stats .card.green').exists()).toBe(false)
    // остальной кабинет работает: статистика и тариф на месте
    expect(w.findAll('.stats-grid .metric').length).toBeGreaterThan(0)
    expect(w.find('.card.plan').exists()).toBe(true)
  })
})
