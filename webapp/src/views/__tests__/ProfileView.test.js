import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'

const fetchMyOrders = vi.fn()
vi.mock('../../api', () => ({
  fetchMyOrders: (...args) => fetchMyOrders(...args),
}))
const { default: ProfileView } = await import('../ProfileView.vue')

describe('ProfileView — профиль покупателя', () => {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/profile', component: ProfileView },
      { path: '/my-orders', component: { template: '<div />' } },
    ],
  })

  beforeEach(() => {
    fetchMyOrders.mockReset()
    router.push('/profile')
  })

  async function mountView() {
    await router.isReady()
    return mount(ProfileView, { global: { plugins: [router] } })
  }

  it('показывает пункты меню и счётчик покупок', async () => {
    fetchMyOrders.mockResolvedValue([
      { id: 1, status: 'paid', total: '10', currency: 'USDT', items: [] },
      { id: 2, status: 'delivered', total: '5', currency: 'USDT', items: [] },
    ])
    const wrapper = await mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('Мои покупки')
    expect(wrapper.text()).toContain('Поддержка')
    expect(wrapper.find('.count').text()).toBe('2')
  })

  it('без ответа API профиль остаётся рабочим, счётчик не показывается', async () => {
    fetchMyOrders.mockRejectedValue(new Error('offline'))
    const wrapper = await mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('Мои покупки')
    expect(wrapper.find('.count').exists()).toBe(false)
  })
})
