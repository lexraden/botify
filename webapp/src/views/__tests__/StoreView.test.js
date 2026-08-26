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

  it('шапка показывает букву магазина и @username', async () => {
    fetchShop.mockResolvedValue({ shop_name: '@petshop', products: PRODUCTS })
    const wrapper = await mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('@petshop')
    // фото бота из Telegram не тянем — Bot API не отдаёт боту его аватарку
    expect(wrapper.find('.shop-id img').exists()).toBe(false)
    expect(wrapper.find('.avatar.letter').text()).toBe('P')
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
