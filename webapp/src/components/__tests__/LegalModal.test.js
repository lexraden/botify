import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import LegalModal from '../LegalModal.vue'
import { PRIVACY } from '../../content/privacy'
import { TOS } from '../../content/tos'
import { setLocale } from '../../services/locale'

describe('LegalModal — модалка юридического документа', () => {
  it('ToS на русском: шапка, предупреждение, нумерация разделов, кап и арбитраж', () => {
    setLocale('ru')
    const w = mount(LegalModal, { props: { docs: TOS } })

    expect(w.find('h3').text()).toBe('Условия использования')
    // юридическое предупреждение в самом начале — про обязательность принятия
    expect(w.find('.notice').text()).toContain('юридически обязывающее соглашение')
    expect(w.find('.notice').text()).toContain('немедленно прекратить пользоваться')
    // разделы нумеруются автоматически, подпункты несут свой номер
    expect(w.find('h4').text()).toBe('1. Принятие условий и изменения')
    // ключевые механизмы на месте
    expect(w.text()).toContain('двадцать долларов США (US$20)')
    expect(w.text()).toContain('индивидуального арбитража')
    expect(w.text()).toContain('отказе от групповых исков')
    w.unmount()
  })

  it('переключатель языка переводит документ на английский', async () => {
    setLocale('ru')
    const w = mount(LegalModal, { props: { docs: TOS } })

    await w.findAll('.switch button').find((b) => b.text() === 'EN').trigger('click')
    expect(w.find('h3').text()).toBe('Terms of Service')
    expect(w.text()).toContain('US$20')
    expect(w.text()).toContain('class action waiver')
    expect(w.text()).toContain('AS IS')
    w.unmount()
  })

  it('Privacy Policy открывается, крестик и клик по фону закрывают', async () => {
    setLocale('ru')
    const w = mount(LegalModal, { props: { docs: PRIVACY } })
    expect(w.find('h3').text()).toBe('Политика конфиденциальности')
    expect(w.text()).toContain('не продаём ваши данные')

    await w.find('.close').trigger('click')
    expect(w.emitted('close')).toHaveLength(1)
    // клик по самой подложке (self), не по листу
    await w.find('.overlay').trigger('click')
    expect(w.emitted('close')).toHaveLength(2)
    w.unmount()
  })
})
