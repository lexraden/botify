import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const fetchSubscription = vi.fn()
const createSubscriptionInvoice = vi.fn()
const openTelegramLink = vi.fn()
vi.mock('../../api', () => ({
  fetchSubscription: (...a) => fetchSubscription(...a),
  createSubscriptionInvoice: (...a) => createSubscriptionInvoice(...a),
}))
vi.mock('../../services/telegram', () => ({
  tg: null,
  openTelegramLink: (...a) => openTelegramLink(...a),
}))
// перехватчик системной «Назад»: проверяем, что лист берёт её себе и отдаёт
const pushBackInterceptor = vi.fn()
const popBackInterceptor = vi.fn()
vi.mock('../../services/backButton', () => ({
  pushBackInterceptor: (...a) => pushBackInterceptor(...a),
  popBackInterceptor: (...a) => popBackInterceptor(...a),
}))

const { default: PlanModal } = await import('../PlanModal.vue')
const { setLocale } = await import('../../services/locale')

const INFO = {
  plan: 'free',
  pro_expires_at: null,
  plus_price_usdt: '20.000000',
  plus_price_stars: 1500,
  pro_price_usdt: '50.000000',
  pro_price_stars: 3750,
  period_days: 30,
  crypto_available: true,
}

describe('PlanModal — окно тарифов', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setLocale('ru')
    fetchSubscription.mockResolvedValue(INFO)
  })

  async function open(reason = null) {
    const w = mount(PlanModal, { props: { reason } })
    await flushPromises()
    return w
  }

  it('тарифы идут от младшего к старшему, каждый со своей ценой', async () => {
    const w = await open('products')
    const tiers = w.findAll('.tier')
    expect(tiers).toHaveLength(2)
    // Plus — младший за 20, Pro — старший за 50 (названия поменяны 2026-09-09)
    expect(tiers[0].text()).toContain('Plus')
    expect(tiers[0].text()).toContain('20 USDT')
    expect(tiers[0].text()).toContain('1500')
    expect(tiers[1].text()).toContain('Pro')
    expect(tiers[1].text()).toContain('50 USDT')
    expect(tiers[1].text()).toContain('3750')
  })

  it('p2p-оплата обещана только в Pro', async () => {
    const w = await open()
    const tiers = w.findAll('.tier')
    expect(tiers[0].text()).not.toContain('реквизит')
    expect(tiers[1].text()).toContain('реквизит')
  })

  it('заголовок называет упёршийся лимит', async () => {
    expect((await open('products')).text()).toContain('товар')
    expect((await open('services')).text()).toContain('услуг')
  })

  it('говорит, что ничего не пропадёт — иначе окно пугает', async () => {
    expect((await open('products')).text()).toContain('Ничего не пропадёт')
  })

  it('оплата в USDT уводит в @CryptoBot', async () => {
    createSubscriptionInvoice.mockResolvedValue({ payment_url: 'https://t.me/CryptoBot?start=x' })
    const w = await open('products')
    await w.findAll('.tier')[1].find('.btn-primary').trigger('click')
    await flushPromises()

    // тариф передаётся тот, чью кнопку нажали
    expect(createSubscriptionInvoice).toHaveBeenCalledWith('crypto', 'pro')
    expect(openTelegramLink).toHaveBeenCalledWith('https://t.me/CryptoBot?start=x')
    expect(w.emitted('close')).toBeTruthy()
  })

  it('без Crypto Pay кнопка USDT неактивна, звёзды остаются', async () => {
    fetchSubscription.mockResolvedValue({ ...INFO, crypto_available: false })
    const w = await open()
    const tier = w.findAll('.tier')[0]
    expect(tier.find('.btn-primary').attributes('disabled')).toBeDefined()
    expect(tier.find('.stars').attributes('disabled')).toBeUndefined()
  })

  it('закрывается крестиком в шапке, кнопки внизу нет', async () => {
    const w = await open()
    // единственная кнопка закрытия — в шапке
    expect(w.findAll('.close')).toHaveLength(1)
    expect(w.find('.head .close').exists()).toBe(true)

    await w.find('.head .close').trigger('click')
    expect(w.emitted('close')).toBeTruthy()
  })

  it('системная «Назад» закрывает лист и отпускается вместе с ним', async () => {
    const w = await open()
    expect(pushBackInterceptor).toHaveBeenCalledTimes(1)

    // именно это backButton.js вызовет вместо перехода назад
    const back = pushBackInterceptor.mock.calls[0][0]
    back()
    expect(w.emitted('close')).toBeTruthy()

    // закрылись — «Назад» снова уводит с экрана, а не висит мёртвым хендлером
    w.unmount()
    expect(popBackInterceptor).toHaveBeenCalledWith(back)
  })

  it('сбой счёта показывается, окно не закрывается', async () => {
    createSubscriptionInvoice.mockRejectedValue({ response: { status: 502, data: { detail: 'invoice_failed' } } })
    const w = await open()
    await w.findAll('.tier')[0].find('.btn-primary').trigger('click')
    await flushPromises()

    expect(w.find('.error').exists()).toBe(true)
    expect(w.emitted('close')).toBeFalsy()
  })
})
