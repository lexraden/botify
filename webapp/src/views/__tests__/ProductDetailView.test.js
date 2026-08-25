import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia } from 'pinia'

const fetchShop = vi.fn()
const fetchProductReviews = vi.fn()
const trackEvent = vi.fn()
vi.mock('../../api', () => ({
  fetchShop: (...args) => fetchShop(...args),
  fetchProductReviews: (...args) => fetchProductReviews(...args),
  trackEvent: (...args) => trackEvent(...args),
}))
const { default: ProductDetailView } = await import('../ProductDetailView.vue')
const { setLocale } = await import('../../services/locale')

const product = {
  id: 7,
  type: 'physical',
  title: 'Кроссовки',
  description: 'Лёгкие, для города',
  image_url: null,
  price: '50',
  currency: 'USDT',
  stock: 3,
  avg_rating: '4.500000',
  reviews_count: 2,
}

describe('ProductDetailView — рейтинг и отзывы на странице товара', () => {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/product/:id', component: ProductDetailView },
    ],
  })

  beforeEach(() => {
    setLocale('ru') // в jsdom navigator.language = en-US, а тесты про русский UI
    fetchShop.mockReset()
    fetchProductReviews.mockReset()
    trackEvent.mockReset()
    router.push('/product/7')
  })

  async function mountView() {
    await router.isReady()
    return mount(ProductDetailView, {
      global: { plugins: [router, createPinia()] },
    })
  }

  it('показывает средний рейтинг и список отзывов', async () => {
    fetchShop.mockResolvedValue({ products: [product] })
    fetchProductReviews.mockResolvedValue([
      {
        rating: 5,
        body: 'Отличное качество',
        author_name: 'Анна К.',
        reply_body: 'Спасибо за отзыв!',
        created_at: '2026-08-20T12:00:00Z',
      },
      { rating: 4, body: null, author_name: null, created_at: '2026-08-21T12:00:00Z' },
    ])
    const wrapper = await mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('★ 4.5 · 2')
    expect(wrapper.text()).toContain('Отзывы')
    expect(wrapper.text()).toContain('Отличное качество')
    // вместо личности — случайный псевдоним
    expect(wrapper.text()).toContain('Анна К.')
    // ответ продавца виден покупателю
    expect(wrapper.text()).toContain('Ответ продавца')
    expect(wrapper.text()).toContain('Спасибо за отзыв!')
    // звёзды отзыва соответствуют оценкам
    const stars = wrapper.findAll('.review .stars').map((s) => s.text())
    expect(stars).toEqual(['★★★★★', '★★★★'])
    wrapper.unmount()
  })

  it('без отзывов секция рейтинга не рисуется', async () => {
    fetchShop.mockResolvedValue({
      products: [{ ...product, avg_rating: null, reviews_count: 0 }],
    })
    fetchProductReviews.mockResolvedValue([])
    const wrapper = await mountView()
    await flushPromises()

    expect(wrapper.find('.reviews').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('★')
    wrapper.unmount()
  })
})
