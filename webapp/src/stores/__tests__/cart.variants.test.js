import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('../../services/telegram', () => ({
  getBotId: () => 1,
  tg: null,
}))

const { useCartStore, lineKey } = await import('../cart')

const RED = { id: 10, attributes: { Цвет: 'Красный' }, price: '5', stock: 3, images: null }
const BLUE = { id: 11, attributes: { Цвет: 'Синий' }, price: '11', stock: 2, images: null }
const SHIRT = { id: 1, title: 'Футболка', type: 'physical', price: '5', stock: 5, variants: [RED, BLUE] }

describe('корзина с вариациями', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })

  it('два размера одного товара — две независимые строки', () => {
    const cart = useCartStore()
    cart.add(SHIRT, RED)
    cart.add(SHIRT, BLUE)
    cart.add(SHIRT, BLUE)

    expect(Object.keys(cart.items)).toHaveLength(2)
    expect(cart.qtyOf(1, RED.id)).toBe(1)
    expect(cart.qtyOf(1, BLUE.id)).toBe(2)
  })

  it('сумма считается по цене вариации, а не товара', () => {
    const cart = useCartStore()
    cart.add(SHIRT, BLUE) // 11, а не витринные «от 5»
    expect(cart.total).toBe(11)
  })

  it('остаток ограничивает вариацию, а не товар целиком', () => {
    const cart = useCartStore()
    for (let i = 0; i < 5; i += 1) cart.add(SHIRT, BLUE)
    // у синей всего 2, хотя у товара суммарно 5
    expect(cart.qtyOf(1, BLUE.id)).toBe(2)
  })

  it('в заказ уходит id выбранной вариации', () => {
    const cart = useCartStore()
    cart.add(SHIRT, RED)
    expect(cart.asOrderItems).toEqual([{ product_id: 1, variant_id: 10, qty: 1 }])
  })

  it('исчезнувшая вариация выпадает из корзины при сверке', () => {
    const cart = useCartStore()
    cart.add(SHIRT, RED)
    cart.add(SHIRT, BLUE)
    // продавец снял красную с продажи
    cart.syncWithShop([{ ...SHIRT, variants: [BLUE] }])

    expect(cart.qtyOf(1, RED.id)).toBe(0)
    expect(cart.qtyOf(1, BLUE.id)).toBe(1)
  })

  it('сверка подрезает количество по новому остатку вариации', () => {
    const cart = useCartStore()
    cart.add(SHIRT, BLUE)
    cart.add(SHIRT, BLUE)
    cart.syncWithShop([{ ...SHIRT, variants: [RED, { ...BLUE, stock: 1 }] }])
    expect(cart.qtyOf(1, BLUE.id)).toBe(1)
  })

  it('старый ключ строки приводится к паре — иначе рядом легла бы вторая', () => {
    // корзина, сохранённая до вариаций: ключ строки — один product_id
    localStorage.setItem(
      'botify-cart:1:anon',
      JSON.stringify({ 1: { product: SHIRT, qty: 2 } }),
    )
    const cart = useCartStore()
    expect(cart.qtyOf(1)).toBe(2)
    expect(Object.keys(cart.items)).toEqual([lineKey(1, null)])
  })
})
