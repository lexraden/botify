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

const { default: PlanModal } = await import('../PlanModal.vue')
const { setLocale } = await import('../../services/locale')

const INFO = {
  plan: 'free',
  pro_expires_at: null,
  price_usdt: '20.000000',
  price_stars: 1500,
  plus_price_usdt: '50.000000',
  plus_price_stars: 3750,
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

  it('показывает оба тарифа с обеими ценами', async () => {
    const w = await open('products')
    const tiers = w.findAll('.tier')
    expect(tiers).toHaveLength(2)
    expect(tiers[0].text()).toContain('Pro')
    expect(tiers[0].text()).toContain('20 USDT')
    expect(tiers[0].text()).toContain('1500')
    expect(tiers[1].text()).toContain('Plus')
    expect(tiers[1].text()).toContain('50 USDT')
    expect(tiers[1].text()).toContain('3750')
  })

  it('p2p-оплата обещана только в Plus', async () => {
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
    expect(createSubscriptionInvoice).toHaveBeenCalledWith('crypto', 'plus')
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

  it('сбой счёта показывается, окно не закрывается', async () => {
    createSubscriptionInvoice.mockRejectedValue({ response: { status: 502, data: { detail: 'invoice_failed' } } })
    const w = await open()
    await w.findAll('.tier')[0].find('.btn-primary').trigger('click')
    await flushPromises()

    expect(w.find('.error').exists()).toBe(true)
    expect(w.emitted('close')).toBeFalsy()
  })
})
