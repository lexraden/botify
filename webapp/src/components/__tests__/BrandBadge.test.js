import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import BrandBadge from '../BrandBadge.vue'

describe('BrandBadge — плашка «Сделано через Botify»', () => {
  it('ведёт на бот Botify', () => {
    const wrapper = mount(BrandBadge)
    const link = wrapper.find('a.made-with')
    expect(link.attributes('href')).toBe('https://t.me/Botifyapp_bot')
    expect(link.text()).toContain('Сделано через')
    expect(link.text()).toContain('Botify')
  })
})
