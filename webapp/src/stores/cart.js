import { defineStore } from 'pinia'
import { getBotId, tg } from '../services/telegram'

// Покупатель на бэкенде — пара (telegram_id, bot_id), и корзина хранится так
// же: отдельно на каждый магазин и на каждого пользователя, чтобы товары не
// смешивались ни между ботами, ни между аккаунтами Telegram на одном
// устройстве. «anon» — браузер и тесты без Telegram-контекста.
function telegramUserId() {
  return tg?.initDataUnsafe?.user?.id ?? 'anon'
}

function storageKey() {
  return `botify-cart:${getBotId() ?? 'default'}:${telegramUserId()}`
}

function legacyKey() {
  return `botify-cart:${getBotId() ?? 'default'}`
}

// Разделение по покупателю добавило telegram_id в ключ (был
// botify-cart:<bot_id>). Старую корзину один раз переносим в новый ключ: на
// устройстве её всё равно создал кто-то один, и забрать её должен именно он.
function loadSavedItems() {
  try {
    const fresh = localStorage.getItem(storageKey())
    if (fresh != null) {
      const parsed = JSON.parse(fresh)
      return parsed && typeof parsed === 'object' ? parsed : {}
    }
    const legacyRaw = localStorage.getItem(legacyKey())
    if (legacyRaw == null) return {}
    const parsed = JSON.parse(legacyRaw)
    const items = parsed && typeof parsed === 'object' ? parsed : {}
    localStorage.removeItem(legacyKey())
    if (Object.keys(items).length) {
      localStorage.setItem(storageKey(), JSON.stringify(items))
    }
    return items
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
