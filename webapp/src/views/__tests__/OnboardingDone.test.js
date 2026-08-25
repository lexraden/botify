import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

const { replaceMock, query } = vi.hoisted(() => ({
  replaceMock: vi.fn(),
  query: { bot: '42', username: 'petshop_bot' },
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query }),
  useRouter: () => ({ replace: replaceMock }),
}))

import OnboardingDone from '../OnboardingDone.vue'
import { setLocale } from '../../services/locale'

// в happy-dom navigator.language = en-US, а тест про русский UI
beforeEach(() => setLocale('ru'))

describe('OnboardingDone — поздравление после создания магазина', () => {
  it('показывает username магазина и уводит «Далее» в магазин', async () => {
    const wrapper = mount(OnboardingDone)
    expect(wrapper.text()).toContain('Магазин создан!')
    expect(wrapper.text()).toContain('@petshop_bot')

    await wrapper.find('.btn-primary').trigger('click')
    expect(replaceMock).toHaveBeenCalledWith('/shop/42')
  })

  it('без данных бота «Далее» ведёт в список магазинов', async () => {
    query.bot = ''
    query.username = ''
    const wrapper = mount(OnboardingDone)

    await wrapper.find('.btn-primary').trigger('click')
    expect(replaceMock).toHaveBeenCalledWith('/shops')
  })
})
