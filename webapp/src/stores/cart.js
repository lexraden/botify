import { defineStore } from 'pinia'
import { getBotId } from '../services/telegram'

// Корзина переживает закрытие Mini App: храним её в localStorage отдельно
// на каждый магазин (bot_id), чтобы товары двух ботов не смешивались.
function storageKey() {
  return `botify-cart:${getBotId() ?? 'default'}`
}

function loadSavedItems() {
  try {
    const raw = localStorage.getItem(storageKey())
    const parsed = raw ? JSON.parse(raw) : null
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {} // битый JSON не должен ломать витрину
  }
}

export const useCartStore = defineStore('cart', {
  state: () => ({
    items: loadSavedItems(), // product_id -> { product, qty }
  }),
  getters: {
    count: (s) => Object.values(s.items).reduce((n, i) => n + i.qty, 0),
    total: (s) =>
      Object.values(s.items).reduce((sum, i) => sum + Number(i.product.price) * i.qty, 0),
    asOrderItems: (s) =>
      Object.values(s.items).map((i) => ({ product_id: i.product.id, qty: i.qty })),
  },
  actions: {
    persist() {
      try {
        localStorage.setItem(storageKey(), JSON.stringify(this.items))
      } catch {
        // приватный режим/переполнение — работаем просто без сохранения
      }
    },
    add(product) {
      const entry = this.items[product.id]
      // stock: null — без ограничения; иначе в корзину не положить больше остатка
      if (product.stock != null && (entry?.qty ?? 0) >= product.stock) return
      if (entry) entry.qty += 1
      else this.items[product.id] = { product, qty: 1 }
      this.persist()
    },
    remove(product) {
      const entry = this.items[product.id]
      if (!entry) return
      entry.qty -= 1
      if (entry.qty <= 0) delete this.items[product.id]
      this.persist()
    },
    // Сверка сохранённой корзины со свежим каталогом (вызывает StoreView после
    // загрузки): удалённые товары выкидываем, цену и сток обновляем, чтобы
    // витрина и чекаут не показывали устаревшие данные.
    syncWithShop(products) {
      const fresh = new Map(products.map((p) => [String(p.id), p]))
      for (const id of Object.keys(this.items)) {
        const actual = fresh.get(id)
        if (!actual) {
          delete this.items[id]
          continue
        }
        const entry = this.items[id]
        entry.product = actual
        if (actual.stock != null && entry.qty > actual.stock) entry.qty = actual.stock
        if (entry.qty <= 0) delete this.items[id]
      }
      this.persist()
    },
    qtyOf(productId) {
      return this.items[productId]?.qty ?? 0
    },
    clear() {
      this.items = {}
      this.persist()
    },
  },
})
