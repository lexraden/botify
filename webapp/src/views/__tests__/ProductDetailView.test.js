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
    // корзина переживает приложение через localStorage — между тестами чистим
    localStorage.clear()
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

  it('зачёркнутая цена показана здесь — и с валютой, как текущая', async () => {
    // из сетки её убрали намеренно: там карточка мелкая, место есть только тут
    fetchShop.mockResolvedValue({
      products: [{ ...product, price: '50', compare_at_price: '80.000000' }],
    })
    fetchProductReviews.mockResolvedValue([])
    const wrapper = await mountView()
    await flushPromises()

    expect(wrapper.find('.price-line .was').text()).toBe('80 USDT')
    expect(wrapper.find('.price-line .price').text()).toBe('50 USDT')
  })

  it('без скидки зачёркнутой цены нет вовсе', async () => {
    fetchShop.mockResolvedValue({ products: [{ ...product, compare_at_price: null }] })
    fetchProductReviews.mockResolvedValue([])
    const wrapper = await mountView()
    await flushPromises()

    expect(wrapper.find('.price-line .was').exists()).toBe(false)
  })

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
    // шапка отзыва: имя слева, дата здесь же; звёзды — отдельной строкой ниже
    const head = wrapper.find('.review .review-head')
    expect(head.find('.author').text()).toBe('Анна К.')
    expect(head.find('.date').exists()).toBe(true)
    const firstReview = wrapper.find('.review').element
    const classes = [...firstReview.children].map((el) => el.className)
    expect(classes.indexOf('review-head')).toBeLessThan(classes.indexOf('stars'))
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

  it('панель покупки в два этажа: добавление сверху, зелёная «В корзину» снизу', async () => {
    fetchShop.mockResolvedValue({ products: [product] })
    fetchProductReviews.mockResolvedValue([])
    const wrapper = await mountView()
    await flushPromises()

    // корзина пуста — только верхний этаж с добавлением
    expect(wrapper.find('.buy-bar .btn-primary').exists()).toBe(true)
    expect(wrapper.find('.buy-bar .stepper').exists()).toBe(false)
    expect(wrapper.find('.buy-bar .btn-green').exists()).toBe(false)

    // добавили — верхний этаж стал степпером количества, снизу появилась зелёная
    await wrapper.find('.buy-bar .btn-primary').trigger('click')
    const floors = [...wrapper.find('.buy-bar').element.children]
    expect(floors[0].className).toBe('stepper')
    expect(floors[1].className).toContain('btn-green')
    wrapper.unmount()
  })

  it('чужой товар в корзине: сверху добавление этого товара, снизу — «В корзину»', async () => {
    fetchShop.mockResolvedValue({ products: [product] })
    fetchProductReviews.mockResolvedValue([])
    await router.isReady()
    // свой экземпляр pinia, чтобы наполнить корзину «другим» товаром
    const pinia = createPinia()
    const wrapper = mount(ProductDetailView, { global: { plugins: [router, pinia] } })
    await flushPromises()

    const { useCartStore } = await import('../../stores/cart')
    useCartStore(pinia).add({ ...product, id: 999, title: 'Другой товар' })
    await flushPromises()

    const floors = [...wrapper.find('.buy-bar').element.children]
    expect(floors[0].className).toContain('btn-primary')
    expect(floors[1].className).toContain('btn-green')
    wrapper.unmount()
  })
})
