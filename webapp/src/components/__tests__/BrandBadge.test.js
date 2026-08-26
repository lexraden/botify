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

  it('живёт в потоке страницы, а не прибита к низу экрана', () => {
    const wrapper = mount(BrandBadge)
    const style = getComputedStyle(wrapper.find('a.made-with').element)
    expect(style.position).not.toBe('fixed')
    expect(style.background).toBe('')
    expect(style.borderRadius).toBe('')
  })
})
