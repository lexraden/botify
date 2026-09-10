import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'

const { default: FeedbackModal } = await import('../FeedbackModal.vue')
const { setLocale } = await import('../../services/locale')

describe('FeedbackModal — «Связаться с нами»', () => {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/profile', component: { template: '<div />' } },
    ],
  })

  beforeEach(() => {
    setLocale('ru')
    // подменяем только setTimeout: полный fake timers ломает микротаски
    // Vue (reactivity), и клики перестают доходить до обработчиков
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    router.push('/profile')
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  async function mountModal(submit) {
    await router.isReady()
    // модалка сама читает экран из роутера — плагин обязателен
    return mount(FeedbackModal, { props: { submit }, global: { plugins: [router] } })
  }

  it('первый шаг — три типа обращения', async () => {
    const w = await mountModal(vi.fn())
    const items = w.findAll('.type-item')
    expect(items).toHaveLength(3)
    expect(w.text()).toContain('Сообщить о проблеме')
    expect(w.text()).toContain('Предложить идею')
    expect(w.text()).toContain('Написать в поддержку')
  })

  it('выбор типа ведёт к форме, отправка вызывает submit с контекстом', async () => {
    const submit = vi.fn().mockResolvedValue()
    const w = await mountModal(submit)

    await w.findAll('.type-item')[1].trigger('click')
    const textarea = w.find('textarea')
    expect(textarea.exists()).toBe(true)

    await textarea.setValue('Хочу купоны')
    await w.find('.btn.send').trigger('click')
    await flushPromises()

    // тип, текст и экран, с которого открыли модалку
    expect(submit).toHaveBeenCalledWith('idea', 'Хочу купоны', '/profile')
    // успех держится на экране пару секунд, затем модалка закрывается сама
    expect(w.text()).toContain('Сообщение отправлено')
    vi.advanceTimersByTime(1800)
    await flushPromises()
    expect(w.emitted('close')).toHaveLength(1)
  })

  it('пустое сообщение отправить нельзя', async () => {
    const submit = vi.fn().mockResolvedValue()
    const w = await mountModal(submit)
    await w.findAll('.type-item')[0].trigger('click')
    expect(w.find('.btn.send').attributes('disabled')).toBeDefined()
    await w.find('.btn.send').trigger('click')
    expect(submit).not.toHaveBeenCalled()
  })

  it('ошибка отправки показывает текст и возвращает форму', async () => {
    const submit = vi.fn().mockRejectedValue(new Error('feedback.error'))
    const w = await mountModal(submit)
    await w.findAll('.type-item')[0].trigger('click')
    await w.find('textarea').setValue('Не работает')
    await w.find('.btn.send').trigger('click')
    await flushPromises()

    expect(w.text()).toContain('Не удалось отправить')
    // форма снова доступна: кнопка не залипла в состоянии «отправляем»
    expect(w.find('.btn.send').attributes('disabled')).toBeUndefined()
  })

  it('флуд-лимит бэкенда показывает свой текст, а не общий', async () => {
    const submit = vi.fn().mockRejectedValue(new Error('feedback.tooMany'))
    const w = await mountModal(submit)
    await w.findAll('.type-item')[2].trigger('click')
    await w.find('textarea').setValue('Ещё раз')
    await w.find('.btn.send').trigger('click')
    await flushPromises()

    expect(w.text()).toContain('Слишком много сообщений')
    expect(w.text()).not.toContain('Не удалось отправить')
  })

  it('«Назад» возвращает к выбору типа', async () => {
    const w = await mountModal(vi.fn())
    await w.findAll('.type-item')[0].trigger('click')
    expect(w.find('textarea').exists()).toBe(true)
    await w.find('.back').trigger('click')
    expect(w.find('textarea').exists()).toBe(false)
    expect(w.findAll('.type-item')).toHaveLength(3)
  })

  it('крестик в шапке закрывает модалку', async () => {
    const w = await mountModal(vi.fn())
    await w.find('.close').trigger('click')
    expect(w.emitted('close')).toHaveLength(1)
  })
})
