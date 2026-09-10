import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const { default: NameEditModal } = await import('../NameEditModal.vue')
const { setLocale } = await import('../../services/locale')

describe('NameEditModal — правка имени покупателя', () => {
  beforeEach(() => setLocale('ru'))

  it('предзаполняется текущим именем', async () => {
    const w = mount(NameEditModal, { props: { initial: 'Алиса', save: vi.fn() } })
    expect(w.find('input').element.value).toBe('Алиса')
  })

  it('сохранение вызывает save с введённым именем и закрывает', async () => {
    const save = vi.fn().mockResolvedValue()
    const w = mount(NameEditModal, { props: { initial: '', save } })
    await w.find('input').setValue('Алиса')
    await w.find('.btn.send').trigger('click')
    await flushPromises()

    expect(save).toHaveBeenCalledWith('Алиса')
    expect(w.emitted('close')).toHaveLength(1)
  })

  it('пустое поле — легальный сброс: кнопка не гаснет', async () => {
    const save = vi.fn().mockResolvedValue()
    const w = mount(NameEditModal, { props: { initial: 'Алиса', save } })
    await w.find('input').setValue('  ')
    expect(w.find('.btn.send').attributes('disabled')).toBeUndefined()

    await w.find('.btn.send').trigger('click')
    await flushPromises()
    // в бэкенд уходит пустая строка — он вернёт имя из Telegram
    expect(save).toHaveBeenCalledWith('')
    expect(w.emitted('close')).toHaveLength(1)
  })

  it('ошибка сохранения показывает текст и оставляет модалку открытой', async () => {
    const save = vi.fn().mockRejectedValue(new Error('offline'))
    const w = mount(NameEditModal, { props: { initial: 'Алиса', save } })
    await w.find('.btn.send').trigger('click')
    await flushPromises()

    expect(w.text()).toContain('Не удалось сохранить')
    expect(w.emitted('close')).toBeUndefined()
    // кнопка снова активна: состояние «сохраняем» не залипло
    expect(w.find('.btn.send').attributes('disabled')).toBeUndefined()
  })

  it('крестик в шапке закрывает модалку', async () => {
    const w = mount(NameEditModal, { props: { initial: '', save: vi.fn() } })
    await w.find('.close').trigger('click')
    expect(w.emitted('close')).toHaveLength(1)
  })
})
