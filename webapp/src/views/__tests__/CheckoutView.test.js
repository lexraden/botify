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
  beforeEach(() => vi.clearAllMocks())

  it('у физического товара спрашивает адрес и не пускает без него', async () => {
    const w = mountWith('physical')
    await flushPromises()
    expect(w.findAll('.delivery input')).toHaveLength(2) // имя и телефон
    expect(w.find('button.pay').attributes('disabled')).toBeDefined()

    await w.find('button.pay').trigger('click')
    expect(createOrder).not.toHaveBeenCalled()
  })

  it('заполненный адрес уходит вместе с заказом', async () => {
    const w = mountWith('physical')
    await flushPromises()
    const [name, phone] = w.findAll('.delivery input')
    await name.setValue('Аня')
    await phone.setValue('+79990001122')
    await w.find('.delivery textarea').setValue('Тверская 1')
    await w.find('button.pay').trigger('click')
    await flushPromises()

    expect(createOrder).toHaveBeenCalledWith(
      [{ product_id: 1, qty: 1 }],
      null,
      { name: 'Аня', phone: '+79990001122', address: 'Тверская 1' },
    )
  })

  it('у цифрового товара блока доставки нет — везти нечего', async () => {
    const w = mountWith('digital')
    await flushPromises()
    expect(w.find('.delivery').exists()).toBe(false)

    await w.find('button.pay').trigger('click')
    await flushPromises()
    expect(createOrder).toHaveBeenCalledWith([{ product_id: 1, qty: 1 }], null, null)
  })
})
