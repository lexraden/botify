import { beforeEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import BrandBadge from '../BrandBadge.vue'
import { setLocale } from '../../services/locale'

describe('BrandBadge — плашка «Сделано через Botify»', () => {
  beforeEach(() => setLocale('ru'))

  it('ведёт на бот Botify', () => {
    const wrapper = mount(BrandBadge)
    const link = wrapper.find('a.made-with')
    expect(link.attributes('href')).toBe('https://t.me/Botifyapp_bot')
    expect(link.text()).toContain('Сделано через')
    expect(link.text()).toContain('Botify')
  })

  it('без закрашенной пилюли и ниже фиксированных панелей', () => {
    const wrapper = mount(BrandBadge)
    const style = getComputedStyle(wrapper.find('a.made-with').element)
    expect(style.background).toBe('')
    expect(style.borderRadius).toBe('')
    expect(Number(style.zIndex)).toBeLessThan(20) // .cart-bar / .pay = 20
  })
})
