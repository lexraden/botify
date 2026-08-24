import { describe, expect, it, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

import TermsModal from '../TermsModal.vue'
import { setLocale } from '../../services/locale'

beforeEach(() => {
  setLocale('ru')
})

describe('TermsModal — язык документа', () => {
  it('по умолчанию показывает русский текст', () => {
    const wrapper = mount(TermsModal)
    expect(wrapper.text()).toContain('Условия использования')
    expect(wrapper.text()).toContain('1. О платформе')
    expect(wrapper.text()).toContain('Комиссии')
  })

  it('переключатель меняет язык документа', async () => {
    const wrapper = mount(TermsModal)
    await wrapper.findAll('.switch button').find((b) => b.text() === 'EN').trigger('click')

    expect(wrapper.text()).toContain('Terms and Conditions')
    expect(wrapper.text()).toContain('1. About the platform')
  })

  it('крестик закрывает модалку', async () => {
    const wrapper = mount(TermsModal)
    await wrapper.find('.close').trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
  })
})
