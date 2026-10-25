import { describe, expect, it, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const { acceptTermsMock, replaceMock, openLinkMock, botPromptMock, closeAppMock } = vi.hoisted(() => ({
  acceptTermsMock: vi.fn(),
  replaceMock: vi.fn(),
  openLinkMock: vi.fn(),
  botPromptMock: vi.fn(),
  closeAppMock: vi.fn(),
}))

vi.mock('../../api', () => ({ acceptTerms: acceptTermsMock, sendBotPrompt: botPromptMock }))
// tg нужен транзитивному i18n (детект языка) — оставляем его пустым
vi.mock('../../services/telegram', () => ({
  tg: null,
  openTelegramLink: openLinkMock,
  closeApp: closeAppMock,
}))
vi.mock('vue-router', () => ({ useRouter: () => ({ replace: replaceMock }) }))

import WelcomeView from '../WelcomeView.vue'
import { setLocale } from '../../services/locale'

function mountView() {
  return mount(WelcomeView)
}

beforeEach(() => {
  vi.clearAllMocks()
  setLocale('ru')
})

describe('WelcomeView — согласие с условиями', () => {
  it('кнопка «Начать» заблокирована, пока чекбокс не отмечен', async () => {
    const wrapper = mountView()
    const button = wrapper.find('.btn-primary')
    expect(button.attributes('disabled')).toBeDefined()

    await wrapper.find('.agree input').setValue(true)
    expect(button.attributes('disabled')).toBeUndefined()
  })

  it('ссылка в дисклеймере открывает модалку с текстом условий', async () => {
    const wrapper = mountView()
    expect(wrapper.find('[role="dialog"]').exists()).toBeFalsy()

    await wrapper.find('.agree a').trigger('click')
    const dialog = wrapper.find('[role="dialog"]')
    expect(dialog.exists()).toBeTruthy()
    expect(dialog.text()).toContain('Условия использования')
    expect(dialog.text()).toContain('1. О платформе')
  })

  it('клик по ссылке не переключает чекбокс', async () => {
    const wrapper = mountView()
    await wrapper.find('.agree a').trigger('click')

    expect(wrapper.find('.agree input').element.checked).toBeFalsy()
  })

  it('после принятия условий сохраняет согласие и переходит к подключению бота', async () => {
    acceptTermsMock.mockResolvedValue({})
    const wrapper = mountView()
    await wrapper.find('.agree input').setValue(true)
    await wrapper.find('.btn-primary').trigger('click')
    await flushPromises()

    expect(acceptTermsMock).toHaveBeenCalledTimes(1)
    expect(replaceMock).toHaveBeenCalledWith('/onboarding/bot')
  })

  it('после галочки сервер присылает кнопку в чат, а приложение закрывается', async () => {
    // Основной путь: никакого диплинка — человек возвращается в тот же чат,
    // где кнопка создания бота уже ждёт
    acceptTermsMock.mockResolvedValue({ create_shop_link: 'https://t.me/botify_bot?start=newshop' })
    botPromptMock.mockResolvedValue({ sent: true })
    closeAppMock.mockReturnValue(true)
    const wrapper = mountView()
    await wrapper.find('.agree input').setValue(true)
    await wrapper.find('.btn-primary').trigger('click')
    await flushPromises()

    expect(botPromptMock).toHaveBeenCalledTimes(1)
    expect(closeAppMock).toHaveBeenCalledTimes(1)
    expect(openLinkMock).not.toHaveBeenCalled()
    expect(replaceMock).not.toHaveBeenCalled()
  })

  it('если сервер кнопку не прислал — уходит в чат диплинком, а не на ввод токена', async () => {
    const link = 'https://t.me/botify_bot?start=newshop'
    acceptTermsMock.mockResolvedValue({ create_shop_link: link })
    botPromptMock.mockResolvedValue({ sent: false })
    const wrapper = mountView()
    await wrapper.find('.agree input').setValue(true)
    await wrapper.find('.btn-primary').trigger('click')
    await flushPromises()

    expect(closeAppMock).not.toHaveBeenCalled()
    expect(openLinkMock).toHaveBeenCalledWith(link)
    expect(replaceMock).not.toHaveBeenCalled()
  })

  it('вне Telegram закрывать нечего — тоже уходит диплинком', async () => {
    const link = 'https://t.me/botify_bot?start=newshop'
    acceptTermsMock.mockResolvedValue({ create_shop_link: link })
    botPromptMock.mockResolvedValue({ sent: true })
    closeAppMock.mockReturnValue(false)
    const wrapper = mountView()
    await wrapper.find('.agree input').setValue(true)
    await wrapper.find('.btn-primary').trigger('click')
    await flushPromises()

    expect(openLinkMock).toHaveBeenCalledWith(link)
  })

  it('при ошибке сохранения показывает сообщение и никуда не ведёт', async () => {
    acceptTermsMock.mockRejectedValue({ response: { data: { detail: 'boom' } } })
    const wrapper = mountView()
    await wrapper.find('.agree input').setValue(true)
    await wrapper.find('.btn-primary').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('boom')
    expect(replaceMock).not.toHaveBeenCalled()
  })
})
