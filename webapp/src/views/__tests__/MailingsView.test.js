import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

// Экран рассылок: форма переезжает из вкладок кабинета сюда, отправка зовёт
// createMailing и обновляет историю. Тест падает без MailingsView.
const createMailing = vi.fn()
const fetchMailings = vi.fn()
vi.mock('../../api', () => ({
  createMailing: (...args) => createMailing(...args),
  fetchMailings: (...args) => fetchMailings(...args),
}))
const routerPush = vi.fn()
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { botId: '1' } }),
  useRouter: () => ({ push: routerPush }),
}))

import MailingsView from '../MailingsView.vue'
const { setLocale } = await import('../../services/locale')

const MAILINGS = [
  {
    id: 3,
    text: 'Скидка 20% на всё до конца недели',
    status: 'done',
    sent_count: 12,
    created_at: '2026-08-27T10:00:00Z',
  },
]

describe('MailingsView — форма и история', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setLocale('ru') // в jsdom navigator.language = en-US, а тесты про русский UI
  })

  it('загружает и показывает историю рассылок', async () => {
    fetchMailings.mockResolvedValue(MAILINGS)
    const w = mount(MailingsView)
    await flushPromises()
    expect(fetchMailings).toHaveBeenCalledWith('1')
    expect(w.text()).toContain('Скидка 20% на всё до конца недели')
    expect(w.text()).toContain('доставлено 12')
    w.unmount()
  })

  it('отправка зовёт createMailing и обновляет список', async () => {
    fetchMailings
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce(MAILINGS)
    createMailing.mockResolvedValue({ id: 3, status: 'pending' })
    const w = mount(MailingsView)
    await flushPromises()

    await w.find('textarea').setValue('Привет!')
    await w.find('.mailing-form .btn').trigger('click')
    await flushPromises()

    expect(createMailing).toHaveBeenCalledWith('1', {
      text: 'Привет!',
      button_text: null,
      button_url: null,
    })
    // форма очистилась, история перезагружена
    expect(w.find('textarea').element.value).toBe('')
    expect(w.text()).toContain('доставлено 12')
    w.unmount()
  })

  it('кнопка неактивна без текста и при половине ссылки', async () => {
    fetchMailings.mockResolvedValue([])
    const w = mount(MailingsView)
    await flushPromises()

    const btn = w.find('.mailing-form .btn')
    expect(btn.attributes('disabled')).toBeDefined()

    await w.find('textarea').setValue('Привет!')
    expect(btn.attributes('disabled')).toBeUndefined()

    await w.find('input[placeholder="Текст кнопки (опционально)"]').setValue('В магазин')
    expect(btn.attributes('disabled')).toBeDefined() // кнопка без ссылки

    await w.find('input[placeholder="Ссылка кнопки"]').setValue('https://t.me/x')
    expect(btn.attributes('disabled')).toBeUndefined()
    w.unmount()
  })
})
