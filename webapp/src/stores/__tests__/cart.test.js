import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useCartStore } from '../cart'

// telegram читается в момент создания store (не при импорте модуля), поэтому
// живого геттера достаточно — пересобирать модуль не нужно
const state = vi.hoisted(() => ({ tg: undefined }))
vi.mock('../../services/telegram', () => ({
  get tg() {
    return state.tg
  },
  getBotId: () => null, // в тестах нет ?bot_id= в адресе
}))

const PRODUCT = { id: 1, title: 'Кофе', price: '3.50', stock: 2 }

// без Telegram-контекста покупатель — «anon», магазин — «default»
const KEY = 'botify-cart:default:anon'

beforeEach(() => {
  localStorage.clear()
  setActivePinia(createPinia())
})

afterEach(() => {
  state.tg = undefined
})

describe('ключ корзины с покупателем', () => {
  it('telegram_id попадает в ключ: разные аккаунты не делят корзину', () => {
    state.tg = { initDataUnsafe: { user: { id: 111 } } }
    const cart = useCartStore()
    cart.add(PRODUCT)
    expect(JSON.parse(localStorage.getItem('botify-cart:default:111'))['1'].qty).toBe(1)
    expect(localStorage.getItem(KEY)).toBe(null)

    state.tg = { initDataUnsafe: { user: { id: 222 } } }
    const other = useCartStore(createPinia()) // fresh pinia = как новое открытие
    expect(other.count).toBe(0)
  })
})

describe('перенос старой корзины (ключ без telegram_id)', () => {
  it('старый ключ переезжает в новый и удаляется', () => {
    localStorage.setItem(
      'botify-cart:default',
      JSON.stringify({ '7': { product: { id: 7, title: 'Чай', price: '1', stock: null }, qty: 2 } }),
    )
    const cart = useCartStore()
    expect(cart.qtyOf(7)).toBe(2)
    expect(localStorage.getItem('botify-cart:default')).toBe(null)
    // перенос записан в новый ключ: следующее открытие читает уже его
    expect(JSON.parse(localStorage.getItem(KEY))['7'].qty).toBe(2)
  })

  it('пустая старая корзина просто удаляется', () => {
    localStorage.setItem('botify-cart:default', JSON.stringify({}))
    const cart = useCartStore()
    expect(cart.count).toBe(0)
    expect(localStorage.getItem('botify-cart:default')).toBe(null)
  })

  it('своя корзина важнее старой: перенос не затирает существующие позиции', () => {
    localStorage.setItem(KEY, JSON.stringify({ '1': { product: PRODUCT, qty: 1 } }))
    localStorage.setItem(
      'botify-cart:default',
      JSON.stringify({ '7': { product: { id: 7, title: 'Чай', price: '1', stock: null }, qty: 2 } }),
    )
    const cart = useCartStore()
    expect(cart.qtyOf(1)).toBe(1)
    expect(cart.qtyOf(7)).toBe(0)
    expect(localStorage.getItem('botify-cart:default')).not.toBe(null) // чужую корзину не трогаем
  })
})

describe('cart — сохранение между открытиями приложения', () => {
  it('add пишет корзину в localStorage', () => {
    const cart = useCartStore()
    cart.add(PRODUCT)
    const saved = JSON.parse(localStorage.getItem(KEY))
    expect(saved['1']).toEqual({ product: PRODUCT, qty: 1 })
  })

  it('новый store подхватывает сохранённую корзину', () => {
    localStorage.setItem(
      KEY,
      JSON.stringify({ '7': { product: { id: 7, title: 'Чай', price: '1', stock: null }, qty: 3 } }),
    )
    const cart = useCartStore(createPinia()) // fresh pinia = как новое открытие
    expect(cart.count).toBe(3)
    expect(cart.total).toBe(3)
    expect(cart.qtyOf(7)).toBe(3)
  })

  it('remove и clear обновляют хранилище', () => {
    const cart = useCartStore()
    cart.add(PRODUCT)
    cart.remove(PRODUCT)
    expect(JSON.parse(localStorage.getItem(KEY))).toEqual({})
    cart.add(PRODUCT)
    cart.clear()
    expect(JSON.parse(localStorage.getItem(KEY))).toEqual({})
    expect(cart.count).toBe(0)
  })

  it('битый JSON не ломает store', () => {
    localStorage.setItem(KEY, '{oops')
    const cart = useCartStore()
    expect(cart.count).toBe(0)
  })
})

describe('syncWithShop — сверка сохранённой корзины с каталогом', () => {
  it('выкидывает удалённые товары и обновляет данные продукта', () => {
    localStorage.setItem(
      KEY,
      JSON.stringify({
        '1': { product: { id: 1, title: 'Старое имя', price: '9.99' }, qty: 1 },
        '5': { product: { id: 5, title: 'Удалён', price: '2' }, qty: 1 },
      }),
    )
    const cart = useCartStore()
    const renamed = { id: 1, title: 'Новое имя', price: '4', stock: null }
    cart.syncWithShop([renamed])
    expect(cart.count).toBe(1)
    expect(cart.items['1'].product.title).toBe('Новое имя')
    expect(cart.total).toBe(4)
  })

  it('обрезает количество по новому стоку, нулевой сток удаляет позицию', () => {
    const cart = useCartStore()
    cart.items['1'] = { product: { ...PRODUCT }, qty: 5 }
    cart.syncWithShop([{ ...PRODUCT, stock: 2 }])
    expect(cart.qtyOf(1)).toBe(2)
    cart.syncWithShop([{ ...PRODUCT, stock: 0 }])
    expect(cart.count).toBe(0)
  })
})
