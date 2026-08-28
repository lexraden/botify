import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

// Модерация отзывов: вкладка «Отзывы» показывает статусы, кнопки зовут API.
// Тест падает без правок — кнопок модерации и вкладки не было.
const approveReview = vi.fn()
const rejectReview = vi.fn()
vi.mock('../../api', () => ({
  approveReview: (...args) => approveReview(...args),
  deleteProduct: vi.fn(),
  deleteShopLogo: vi.fn(),
  fetchMe: vi.fn(() => Promise.resolve({})),
  fetchProducts: vi.fn(() => Promise.resolve([])),
  fetchSellerReviews: vi.fn(() => Promise.resolve(REVIEWS)),
  fetchShopOrders: vi.fn(() => Promise.resolve([])),
  fetchShopStats: vi.fn(() => Promise.resolve({})),
  fetchShopSummary: vi.fn(() => Promise.resolve(SUMMARY)),
  fulfillOrder: vi.fn(),
  rejectReview: (...args) => rejectReview(...args),
  replyToReview: vi.fn(),
  sendOrderChatPhoto: vi.fn(),
  updateShopName: vi.fn(),
  uploadShopLogo: vi.fn(),
  withdrawPayout: vi.fn(),
}))
const routerPush = vi.fn()
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { botId: '1' }, query: { tab: 'reviews' } }),
  useRouter: () => ({ push: routerPush }),
}))
vi.mock('../../services/telegram', () => ({ openTelegramLink: vi.fn(), tg: undefined }))

import ShopView from '../ShopView.vue'
const { setLocale } = await import('../../services/locale')

const SUMMARY = {
  shop_name: 'Магазин',
  logo_url: null,
  payout_pending: 0,
  payout_paid: 0,
  payout_min: 0,
}

// один ожидает решения, один скрыт продавцом, один опубликован
const REVIEWS = [
  {
    id: 11,
    order_id: 101,
    product_title: 'Кружка',
    author_name: 'Аноним',
    rating: 2,
    body: 'Разочарован',
    status: 'pending',
    moderated_at: null,
    reply_body: null,
    reply_at: null,
    created_at: '2026-08-27T10:00:00Z',
  },
  {
    id: 12,
    order_id: 102,
    product_title: 'Кружка',
    author_name: 'Аноним',
    rating: 1,
    body: 'Грубиян',
    status: 'rejected',
    moderated_at: '2026-08-27T11:00:00Z',
    reply_body: null,
    reply_at: null,
    created_at: '2026-08-27T10:00:00Z',
  },
  {
    id: 13,
    order_id: 103,
    product_title: 'Кружка',
    author_name: 'Аноним',
    rating: 5,
    body: 'Отлично',
    status: 'published',
    moderated_at: '2026-08-27T10:00:00Z',
    reply_body: null,
    reply_at: null,
    created_at: '2026-08-27T10:00:00Z',
  },
]

async function mountReviews() {
  const w = mount(ShopView)
  await flushPromises()
  return w
}

describe('ShopView — вкладка отзывов и модерация', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setLocale('ru') // в jsdom navigator.language = en-US, а тесты про русский UI
  })

  it('статусы: «На проверке», «Скрыт», опубликованный без пометки', async () => {
    const w = await mountReviews()
    expect(w.text()).toContain('На проверке')
    expect(w.text()).toContain('Скрыт')
    // опубликованный отзыв виден без бейджа: текст есть, статуса нет
    expect(w.text()).toContain('Отлично')
    w.unmount()
  })

  it('имя, затем звёзды; заказ справа в строке имени, товар под ним', async () => {
    const w = await mountReviews()
    const reviews = w.findAll('.seller-review')
    expect(reviews.map((r) => r.find('.sr-head .stars').text())).toEqual([
      'Аноним · ★★',
      'Аноним · ★',
      'Аноним · ★★★★★',
    ])
    // номер заказа — справа в строке имени, товар — под ней
    expect(reviews.map((r) => r.find('.sr-head .sr-order').text())).toEqual([
      'Заказ #101',
      'Заказ #102',
      'Заказ #103',
    ])
    expect(reviews.map((r) => r.find('.sr-meta').text())).toEqual([
      'Кружка',
      'Кружка',
      'Кружка',
    ])
    w.unmount()
  })

  it('у ожидающего две кнопки: «Одобрить» публикует, «Скрыть» отклоняет', async () => {
    const w = await mountReviews()
    const pending = w.findAll('.seller-review')[0]
    const buttons = pending.findAll('.mod-actions button')
    expect(buttons).toHaveLength(2)
    expect(buttons[0].text()).toBe('Скрыть')
    expect(buttons[1].text()).toBe('Одобрить')

    approveReview.mockResolvedValue({ ...REVIEWS[0], status: 'published' })
    await buttons[1].trigger('click')
    await flushPromises()
    expect(approveReview).toHaveBeenCalledWith('1', 11)
    // статус обновился на месте — бейдж исчез, кнопки тоже
    expect(pending.find('.sr-status').exists()).toBe(false)
    expect(pending.find('.mod-actions').exists()).toBe(false)
    w.unmount()
  })

  it('«Скрыть» зовёт rejectReview', async () => {
    const w = await mountReviews()
    const pending = w.findAll('.seller-review')[0]
    rejectReview.mockResolvedValue({ ...REVIEWS[0], status: 'rejected' })
    await pending.findAll('.mod-actions button')[0].trigger('click')
    await flushPromises()
    expect(rejectReview).toHaveBeenCalledWith('1', 11)
    w.unmount()
  })

  it('у скрытого одна кнопка «Опубликовать»', async () => {
    const w = await mountReviews()
    const rejected = w.findAll('.seller-review')[1]
    const buttons = rejected.findAll('.mod-actions button')
    expect(buttons).toHaveLength(1)
    expect(buttons[0].text()).toBe('Опубликовать')
    approveReview.mockResolvedValue({ ...REVIEWS[1], status: 'published' })
    await buttons[0].trigger('click')
    await flushPromises()
    expect(approveReview).toHaveBeenCalledWith('1', 12)
    w.unmount()
  })

  it('опубликованный отзыв без кнопок модерации', async () => {
    const w = await mountReviews()
    expect(w.findAll('.seller-review')[2].find('.mod-actions').exists()).toBe(false)
    w.unmount()
  })

  it('рассылки открылись отдельным экраном, вкладки mailings больше нет', async () => {
    const w = await mountReviews()
    // кнопка-рупор в шапке ведёт на /shop/1/mailings
    const megaphone = w.find('header .controls .icon-btn:first-child')
    await megaphone.trigger('click')
    expect(routerPush).toHaveBeenCalledWith('/shop/1/mailings')

    // вкладок четыре, «Рассылки» среди них больше нет
    const navButtons = w.findAll('nav button')
    expect(navButtons.map((b) => b.text())).toEqual(['Товары', 'Заказы', 'Отзывы', 'Статистика'])
    w.unmount()
  })
})
