import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'

const fetchMe = vi.fn()
vi.mock('../../api', () => ({
  fetchMe: (...args) => fetchMe(...args),
  deleteShop: vi.fn(),
  disableShop: vi.fn(),
  enableShop: vi.fn(),
}))
const { default: ShopsView } = await import('../ShopsView.vue')

// Черновик — магазин, заведённый через /newshop до создания бота. У него нет
// юзернейма, и раньше карточка звала bot_username.charAt(0): весь список
// магазинов падал с TypeError. Роутер ведёт сюда как раз в этом случае —
// неактивный магазин или второй магазин у продавца.
const DRAFT = {
  id: 7,
  bot_username: null,
  title: 'Кофейня у дома',
  is_draft: true,
  is_active: false,
  webhook_status: 'pending',
}
const LIVE = {
  id: 8,
  bot_username: 'petshop_bot',
  title: 'Зоомагазин',
  is_draft: false,
  is_active: true,
  webhook_status: 'active',
}

describe('ShopsView — черновик в списке магазинов', () => {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/shops', component: ShopsView },
      { path: '/shop/:botId', component: { template: '<div />' } },
      { path: '/onboarding/bot', component: { template: '<div />' } },
    ],
  })

  beforeEach(() => {
    fetchMe.mockReset()
  })

  async function mountShops(bots) {
    fetchMe.mockResolvedValue({ bots })
    router.push('/shops')
    await router.isReady()
    const wrapper = mount(ShopsView, { global: { plugins: [router] } })
    await flushPromises()
    return wrapper
  }

  it('рисует черновик, а не падает на пустом юзернейме', async () => {
    const wrapper = await mountShops([LIVE, DRAFT])
    const text = wrapper.text()

    // главное: экран вообще отрисовался и рабочий магазин на месте
    expect(text).toContain('@petshop_bot')
    // черновик подписан названием, которое продавец ввёл в /newshop
    expect(text).toContain('Кофейня у дома')
    expect(text).not.toContain('@null')
    expect(wrapper.findAll('.card.shop')).toHaveLength(2)
  })

  it('у черновика в аватарке буква названия, а не сбой', async () => {
    const wrapper = await mountShops([DRAFT])
    expect(wrapper.find('.avatar').text()).toBe('К')
  })

  it('черновик не предлагает «Включить» — бэкенд такую попытку отклоняет', async () => {
    const wrapper = await mountShops([DRAFT])
    await wrapper.find('.menu-btn').trigger('click')

    const buttons = wrapper.findAll('.actions .btn').map((b) => b.text())
    expect(buttons.some((label) => /Включить|Enable/i.test(label))).toBe(false)
    // удалить брошенный черновик по-прежнему можно
    expect(buttons.some((label) => /Удалить|Delete/i.test(label))).toBe(true)
  })
})
