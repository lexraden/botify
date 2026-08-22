import { defineStore } from 'pinia'

export const useCartStore = defineStore('cart', {
  state: () => ({
    items: {}, // product_id -> { product, qty }
  }),
  getters: {
    count: (s) => Object.values(s.items).reduce((n, i) => n + i.qty, 0),
    total: (s) =>
      Object.values(s.items).reduce((sum, i) => sum + Number(i.product.price) * i.qty, 0),
    asOrderItems: (s) =>
      Object.values(s.items).map((i) => ({ product_id: i.product.id, qty: i.qty })),
  },
  actions: {
    add(product) {
      const entry = this.items[product.id]
      // stock: null — без ограничения; иначе в корзину не положить больше остатка
      if (product.stock != null && (entry?.qty ?? 0) >= product.stock) return
      if (entry) entry.qty += 1
      else this.items[product.id] = { product, qty: 1 }
    },
    remove(product) {
      const entry = this.items[product.id]
      if (!entry) return
      entry.qty -= 1
      if (entry.qty <= 0) delete this.items[product.id]
    },
    qtyOf(productId) {
      return this.items[productId]?.qty ?? 0
    },
    clear() {
      this.items = {}
    },
  },
})
