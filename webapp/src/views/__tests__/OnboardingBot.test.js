import { describe, expect, it, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const { fetchMeMock, connectBotMock, openLinkMock, replaceMock } = vi.hoisted(() => ({
  fetchMeMock: vi.fn(),
  connectBotMock: vi.fn(),
  openLinkMock: vi.fn(),
  replaceMock: vi.fn(),
}))

vi.mock('../../api', () => ({ fetchMe: fetchMeMock, connectBot: connectBotMock }))
// tg нужен транзитивному i18n (детект языка) — оставляем его пустым
vi.mock('../../services/telegram', () => ({ tg: null, openTelegramLink: openLinkMock }))
vi.mock('vue-router', () => ({ useRouter: () => ({ replace: replaceMock }) }))

import OnboardingBot from '../OnboardingBot.vue'
import { setLocale } from '../../services/locale'

const LINK = 'https://t.me/botify_bot?start=newshop'

async function mountView(me = {}) {
  fetchMeMock.mockResolvedValue({ bots: [], cryptobot_connected: false, ...me })
  const wrapper = mount(OnboardingBot)
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  setLocale('ru')
})

describe('OnboardingBot — создание магазина силами Telegram', () => {
  it('когда ссылка есть, поле токена и BotFather спрятаны', async () => {
    const wrapper = await mountView({ create_shop_link: LINK })

    expect(wrapper.find('input.token').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('BotFather')
    expect(wrapper.find('.btn-primary').text()).toBe('Создать магазин')
  })

  it('главная кнопка уводит в переписку с hub-ботом', async () => {
    const wrapper = await mountView({ create_shop_link: LINK })
    await wrapper.find('.btn-primary').trigger('click')

    expect(openLinkMock).toHaveBeenCalledWith(LINK)
  })

  it('«у меня уже есть бот» открывает ручной ввод токена', async () => {
    const wrapper = await mountView({ create_shop_link: LINK })
    await wrapper.find('.have-bot a').trigger('click')

    expect(wrapper.find('input.token').exists()).toBe(true)
    expect(wrapper.text()).toContain('BotFather')
  })

  it('без ссылки ручной путь остаётся единственным и открыт сразу', async () => {
    const wrapper = await mountView()

    expect(wrapper.find('input.token').exists()).toBe(true)
    expect(wrapper.find('.have-bot').exists()).toBe(false)
  })

  it('ручной ввод токена по-прежнему подключает бота', async () => {
    connectBotMock.mockResolvedValue({ ok: true, bot: { id: 7, bot_username: 'shop_bot' } })
    const wrapper = await mountView({ create_shop_link: LINK })
    await wrapper.find('.have-bot a').trigger('click')
    await wrapper.find('input.token').setValue('1234567890:AA')
    await wrapper.find('.btn-primary').trigger('click')
    await flushPromises()

    expect(connectBotMock).toHaveBeenCalledWith('1234567890:AA')
    expect(replaceMock).toHaveBeenCalledWith('/onboarding/done?bot=7&username=shop_bot')
  })
})
