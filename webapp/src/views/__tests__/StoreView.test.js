import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia } from 'pinia'

const fetchShop = vi.fn()
const trackEvent = vi.fn()
vi.mock('../../api', () => ({
  fetchShop: (...args) => fetchShop(...args),
  trackEvent: (...args) => trackEvent(...args),
}))
const { default: StoreView } = await import('../StoreView.vue')
const { setLocale } = await import('../../services/locale')

const PRODUCTS = [
  { id: 1, title: 'Кофе', description: 'свежая обжарка', price: '10', stock: 5 },
  { id: 2, title: 'Кружка', description: null, price: '7', stock: null },
]

describe('StoreView — шапка магазина и поиск', () => {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: StoreView },
      { path: '/profile', component: { template: '<div />' } },
      { path: '/checkout', component: { template: '<div />' } },
    ],
  })

  beforeEach(() => {
    fetchShop.mockReset()
    trackEvent.mockReset()
    setLocale('ru')
    router.push('/')
  })

  async function mountView() {
    await router.isReady()
    return mount(StoreView, {
      global: {
        plugins: [router, createPinia()],
        stubs: {
          ProductCard: { props: ['product'], template: '<div class="stub-card">{{ product.title }}</div>' },
        },
      },
    })
  }

  it('хиро: буква-аватар, имя магазина, trust-строка с рейтингом и продажами', async () => {
    fetchShop.mockResolvedValue({
      shop_name: 'Shopik',
      logo_url: null,
      rating: 4.9,
      sales_count: 12,
      products: PRODUCTS,
    })
    const wrapper = await mountView()
    await flushPromises()
    // без лого — кружок с первой буквой названия
    const letter = wrapper.find('.avatar.letter')
    expect(letter.exists()).toBe(true)
    expect(letter.text()).toBe('S')
    // показное имя вместо прежнего заголовка «Магазин»
    expect(wrapper.find('.shop-id h2').text()).toBe('Shopik')
    // trust-строка: ★ 4.9 · 12 продаж (звезда отдельным элементом)
    const trustText = wrapper.find('.trust').text().replace(/\s+/g, ' ').trim()
    expect(trustText).toBe('★4.9 · 12 продаж')
    expect(wrapper.find('.trust .star').text()).toBe('★')
  })

  it('лого рисуется картинкой по адресу из ответа', async () => {
    fetchShop.mockResolvedValue({
      shop_name: 'Shopik',
      logo_url: '/api/shop-logos/tok123',
      rating: null,
      sales_count: 12,
      products: PRODUCTS,
    })
    const wrapper = await mountView()
    await flushPromises()
    const img = wrapper.find('.avatar')
    expect(img.element.tagName).toBe('IMG')
    expect(img.attributes('src')).toBe('/api/shop-logos/tok123')
  })

  it('без продаж trust-строки нет вовсе; продажи без отзывов — без рейтинга', async () => {
    fetchShop.mockResolvedValue({
      shop_name: 'Магазин',
      logo_url: null,
      rating: null,
      sales_count: 0,
      products: PRODUCTS,
    })
    let wrapper = await mountView()
    await flushPromises()
    expect(wrapper.find('.trust').exists()).toBe(false)

    // продажи есть, отзывов нет: число показано, рейтинга и звезды нет
    fetchShop.mockResolvedValue({
      shop_name: 'Магазин',
      logo_url: null,
      rating: null,
      sales_count: 1,
      products: PRODUCTS,
    })
    wrapper.unmount()
    wrapper = await mountView()
    await flushPromises()
    const trust = wrapper.find('.trust')
    expect(trust.text().replace(/\s+/g, ' ').trim()).toBe('1 продажа') // единица — не «продажи»
    expect(trust.find('.star').exists()).toBe(false)
  })

  it('поиск фильтрует каталог по названию и описанию', async () => {
    fetchShop.mockResolvedValue({ shop_name: '@petshop', products: PRODUCTS })
    const wrapper = await mountView()
    await flushPromises()
    expect(wrapper.findAll('.stub-card')).toHaveLength(2)

    await wrapper.find('.controls button').trigger('click')
    await wrapper.find('.search-row input').setValue('круж')
    expect(wrapper.findAll('.stub-card')).toHaveLength(1)
    expect(wrapper.text()).toContain('Кружка')

    // описание тоже ищется
    await wrapper.find('.search-row input').setValue('обжарка')
    expect(wrapper.text()).toContain('Кофе')

    await wrapper.find('.search-row input').setValue('несуществующее')
    expect(wrapper.findAll('.stub-card')).toHaveLength(0)
    expect(wrapper.text()).toContain('Ничего не нашлось')
  })

  it('крестик сбрасывает поиск и возвращает весь каталог', async () => {
    fetchShop.mockResolvedValue({ shop_name: '@petshop', products: PRODUCTS })
    const wrapper = await mountView()
    await flushPromises()

    await wrapper.find('.controls button').trigger('click')
    await wrapper.find('.search-row input').setValue('круж')
    expect(wrapper.findAll('.stub-card')).toHaveLength(1)

    await wrapper.find('.search-row .clear').trigger('click')
    expect(wrapper.findAll('.stub-card')).toHaveLength(2)
    expect(wrapper.find('.search-row input').element.value).toBe('')
  })
})
