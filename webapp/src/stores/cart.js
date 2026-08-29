import { defineStore } from 'pinia'
import { getBotId, tg } from '../services/telegram'

// Покупатель на бэкенде — пара (telegram_id, bot_id), и корзина хранится так
// же: отдельно на каждый магазин и на каждого пользователя, чтобы товары не
// смешивались ни между ботами, ни между аккаунтами Telegram на одном
// устройстве. «anon» — браузер и тесты без Telegram-контекста.
function telegramUserId() {
  return tg?.initDataUnsafe?.user?.id ?? 'anon'
}

// Строка корзины — это пара «товар + вариация»: одна и та же футболка в двух
// размерах покупается двумя строками, с независимыми ценой и остатком.
// Товар без вариаций даёт пустую половину ключа.
export function lineKey(productId, variantId) {
  return `${productId}:${variantId ?? ''}`
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
// До вариаций строка корзины ключевалась одним product_id. Такие корзины уже
// лежат у покупателей в браузерах: без приведения qtyOf их не нашёл бы, а
// add завёл бы рядом вторую строку того же товара.
function normalizeKeys(items) {
  const out = {}
  for (const [key, entry] of Object.entries(items)) {
    if (!entry || typeof entry !== 'object' || !entry.product) continue
    out[key.includes(':') ? key : lineKey(entry.product.id, entry.variant?.id)] = entry
  }
  return out
}

function loadSavedItems() {
  try {
    const fresh = localStorage.getItem(storageKey())
    if (fresh != null) {
      const parsed = JSON.parse(fresh)
      return parsed && typeof parsed === 'object' ? normalizeKeys(parsed) : {}
    }
    const legacyRaw = localStorage.getItem(legacyKey())
    if (legacyRaw == null) return {}
    const parsed = JSON.parse(legacyRaw)
    const items = parsed && typeof parsed === 'object' ? normalizeKeys(parsed) : {}
    localStorage.removeItem(legacyKey())
    if (Object.keys(items).length) {
      localStorage.setItem(storageKey(), JSON.stringify(items))
    }
    return items
  } catch {
    return {} // битый JSON не должен ломать витрину
  }
}

// Откуда брать цену и остаток строки: у товара с вариацией — из вариации
function source(entry) {
  return entry.variant ?? entry.product
}

export const useCartStore = defineStore('cart', {
  state: () => ({
    items: loadSavedItems(), // "productId:variantId" -> { product, variant, qty }
  }),
  getters: {
    count: (s) => Object.values(s.items).reduce((n, i) => n + i.qty, 0),
    total: (s) =>
      Object.values(s.items).reduce((sum, i) => sum + Number(source(i).price) * i.qty, 0),
    asOrderItems: (s) =>
      Object.values(s.items).map((i) => ({
        product_id: i.product.id,
        variant_id: i.variant?.id ?? null,
        qty: i.qty,
      })),
  },
  actions: {
    persist() {
      try {
        localStorage.setItem(storageKey(), JSON.stringify(this.items))
      } catch {
        // приватный режим/переполнение — работаем просто без сохранения
      }
    },
    add(product, variant = null) {
      const key = lineKey(product.id, variant?.id)
      const entry = this.items[key]
      const stock = (variant ?? product).stock
      // stock: null — без ограничения; иначе в корзину не положить больше остатка
      if (stock != null && (entry?.qty ?? 0) >= stock) return
      if (entry) entry.qty += 1
      else this.items[key] = { product, variant, qty: 1 }
      this.persist()
    },
    remove(product, variant = null) {
      const key = lineKey(product.id, variant?.id)
      const entry = this.items[key]
      if (!entry) return
      entry.qty -= 1
      if (entry.qty <= 0) delete this.items[key]
      this.persist()
    },
    // Сверка сохранённой корзины со свежим каталогом (вызывает StoreView после
    // загрузки): удалённые товары выкидываем, цену и сток обновляем, чтобы
    // витрина и чекаут не показывали устаревшие данные.
    syncWithShop(products) {
      const fresh = new Map(products.map((p) => [String(p.id), p]))
      for (const key of Object.keys(this.items)) {
        const entry = this.items[key]
        const actual = fresh.get(String(entry.product.id))
        if (!actual) {
          delete this.items[key]
          continue
        }
        entry.product = actual
        if (entry.variant) {
          // вариацию могли снять с продажи или удалить — тогда покупать нечего
          const variant = (actual.variants || []).find((v) => v.id === entry.variant.id)
          if (!variant) {
            delete this.items[key]
            continue
          }
          entry.variant = variant
        }
        const stock = (entry.variant ?? actual).stock
        if (stock != null && entry.qty > stock) entry.qty = stock
        if (entry.qty <= 0) delete this.items[key]
      }
      this.persist()
    },
    qtyOf(productId, variantId = null) {
      return this.items[lineKey(productId, variantId)]?.qty ?? 0
    },
    clear() {
      this.items = {}
      this.persist()
    },
  },
})
