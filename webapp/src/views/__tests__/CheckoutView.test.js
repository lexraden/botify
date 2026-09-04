import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('../../api', () => ({
  createOrder: vi.fn(() => Promise.resolve({ id: 1, payment_url: null })),
  trackEvent: vi.fn(),
}))
vi.mock('../../services/telegram', () => ({
  tg: null,
  getBotId: () => 1,
  getInitData: () => '',
  initTelegram: () => {},
  openTelegramLink: () => {},
}))

import { createOrder } from '../../api'
import CheckoutView from '../CheckoutView.vue'
import { useCartStore } from '../../stores/cart'

const router = { push: vi.fn() }
vi.mock('vue-router', () => ({ useRouter: () => router }))

function mountWith(type) {
  setActivePinia(createPinia())
  const cart = useCartStore()
  cart.items = { 1: { product: { id: 1, title: 'Кружка', price: '5', type }, qty: 1 } }
  return mount(CheckoutView)
}

describe('CheckoutView — доставка', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    delete window.Telegram
    window.open = vi.fn()
  })

  it('у физического товара одно поле адреса, без него оплата не пускает', async () => {
    const w = mountWith('physical')
    await flushPromises()
    expect(w.findAll('.delivery textarea')).toHaveLength(1) // имя и телефон убрали
    expect(w.find('button.pay').attributes('disabled')).toBeDefined()

    await w.find('button.pay').trigger('click')
    expect(createOrder).not.toHaveBeenCalled()
  })

  it('заполненный адрес уходит вместе с заказом', async () => {
    const w = mountWith('physical')
    await flushPromises()
    await w.find('.delivery textarea').setValue('Тверская 1')
    await w.find('button.pay').trigger('click')
    await flushPromises()

    expect(createOrder).toHaveBeenCalledWith(
      [{ product_id: 1, variant_id: null, qty: 1 }],
      null,
      { address: 'Тверская 1' },
    )
  })

  it('у цифрового товара блока доставки нет — везти нечего', async () => {
    const w = mountWith('digital')
    await flushPromises()
    expect(w.find('.delivery').exists()).toBe(false)

    await w.find('button.pay').trigger('click')
    await flushPromises()
    expect(createOrder).toHaveBeenCalledWith([{ product_id: 1, variant_id: null, qty: 1 }], null, null)
  })

  it('после Pay открывается окно оплаты, а покупатель — в «Моих покупках»', async () => {
    createOrder.mockResolvedValueOnce({ id: 1, payment_url: 'https://t.me/CryptoBot' })
    window.Telegram = { WebApp: { openTelegramLink: vi.fn() } }
    const w = mountWith('digital')
    await flushPromises()
    await w.find('button.pay').trigger('click')
    await flushPromises()

    expect(window.Telegram.WebApp.openTelegramLink).toHaveBeenCalledWith('https://t.me/CryptoBot')
    expect(window.open).not.toHaveBeenCalled()
    // вернувшись из @CryptoBot, человек должен увидеть свою покупку и её
    // статус, а не каталог, из которого он ушёл
    expect(router.push).toHaveBeenCalledWith({
      path: '/my-orders',
      query: { created: 1, pay: '1' },
    })
  })
})

describe('CheckoutView — строка с вариацией', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
  })

  function withVariant(variant) {
    const cart = useCartStore()
    cart.items = {
      '1:9': {
        product: { id: 1, title: 'Футболка красная', price: '5', type: 'physical' },
        variant: { id: 9, price: '7', attributes: { Цвет: 'Синий' }, ...variant },
        qty: 1,
      },
    }
    return mount(CheckoutView)
  }

  it('имя строки — от вариации: товарное принадлежит первой', async () => {
    const w = withVariant({ title: 'Футболка синяя' })
    await flushPromises()
    expect(w.find('.row .info b').text()).toBe('Футболка синяя')
    expect(w.find('.row .variant').text()).toBe('Синий')
  })

  it('у вариации без своего имени остаётся товарное', async () => {
    const w = withVariant({ title: null })
    await flushPromises()
    expect(w.find('.row .info b').text()).toBe('Футболка красная')
  })
})

describe('CheckoutView — счёт не создался', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    delete window.Telegram
    window.open = vi.fn()
  })

  it('покупателя ведут в «Мои покупки», а не молча в каталог', async () => {
    // Бэкенд намеренно сохраняет заказ, когда Crypto Pay недоступен, и
    // отдаёт payment_url: null. Раньше корзина очищалась, окно оплаты не
    // открывалось и router.push('/') уводил покупателя в каталог — про
    // неоплаченный заказ он не узнавал вообще.
    createOrder.mockResolvedValueOnce({ id: 42, payment_url: null })
    const w = mountWith('digital')
    await flushPromises()
    await w.find('button.pay').trigger('click')
    await flushPromises()

    expect(window.open).not.toHaveBeenCalled()
    expect(router.push).toHaveBeenCalledWith({
      path: '/my-orders',
      query: { created: 42, pay: '0' },
    })
  })

  it('со ссылкой на оплату открывает её и ведёт в «Мои покупки»', async () => {
    createOrder.mockResolvedValueOnce({ id: 43, payment_url: 'https://t.me/CryptoBot?start=x' })
    const w = mountWith('digital')
    await flushPromises()
    await w.find('button.pay').trigger('click')
    await flushPromises()

    expect(window.open).toHaveBeenCalledWith('https://t.me/CryptoBot?start=x', '_blank')
    expect(router.push).toHaveBeenCalledWith({
      path: '/my-orders',
      query: { created: 43, pay: '1' },
    })
  })
})
