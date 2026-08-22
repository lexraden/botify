<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchShop, trackEvent } from '../api'
import { useCartStore } from '../stores/cart'

const route = useRoute()
const router = useRouter()
const cart = useCartStore()
const product = ref(null)
const error = ref('')

const emoji = computed(
  () => ({ physical: '📦', digital: '📕', service: '🛎' })[product.value?.type] ?? '📦',
)
const soldOut = computed(() => product.value?.stock === 0)
const qty = computed(() => (product.value ? cart.qtyOf(product.value.id) : 0))
const maxed = computed(
  () => product.value?.stock != null && qty.value >= product.value.stock,
)

onMounted(async () => {
  try {
    const shop = await fetchShop()
    product.value = shop.products.find((p) => p.id === Number(route.params.id)) || null
    if (!product.value) {
      error.value = 'Товар не найден'
      return
    }
    trackEvent('product_view', product.value.id)
  } catch (e) {
    error.value = e.response?.data?.detail || 'Не удалось загрузить товар'
  }
})
</script>

<template>
  <div class="detail">
    <a class="back" @click="router.push('/')">← В каталог</a>

    <template v-if="product">
      <div class="photo">
        <img v-if="product.image_url" :src="product.image_url" :alt="product.title" />
        <span v-else>{{ emoji }}</span>
      </div>

      <h2>{{ product.title }}</h2>
      <div class="price-line">
        <b class="price">{{ Number(product.price) }} USDT</b>
        <span v-if="soldOut" class="state soldout">Нет в наличии</span>
        <span v-else-if="product.stock != null" class="state">Осталось: {{ product.stock }}</span>
      </div>

      <p v-if="product.description" class="desc">{{ product.description }}</p>

      <div v-if="qty" class="stepper">
        <button @click="cart.remove(product)">−</button>
        <b>{{ qty }}</b>
        <button :disabled="maxed" @click="cart.add(product)">+</button>
      </div>
      <button
        v-else-if="!soldOut"
        class="btn btn-primary"
        @click="cart.add(product)"
      >
        Добавить в корзину
      </button>
      <button v-else class="btn btn-soft" disabled>Нет в наличии</button>

      <button v-if="cart.count" class="btn btn-green go-cart" @click="router.push('/checkout')">
        В корзину · {{ cart.count }} · {{ cart.total.toFixed(2) }} USDT
      </button>
    </template>

    <p v-else-if="error" class="error">{{ error }}</p>
  </div>
</template>

<style scoped>
.detail { padding: 18px 16px 40px; }
.back { display: inline-block; margin-bottom: 14px; color: var(--sub); font-size: 14px; font-weight: 700; cursor: pointer; }
.photo {
  width: 100%; aspect-ratio: 1; border-radius: 18px; background: var(--surface2);
  display: flex; align-items: center; justify-content: center; font-size: 72px;
  overflow: hidden;
}
.photo img { width: 100%; height: 100%; object-fit: cover; }
h2 { font-size: 19px; margin: 14px 0 6px; }
.price-line { display: flex; align-items: baseline; gap: 10px; }
.price { font-size: 20px; }
.state { font-size: 13px; color: var(--sub); font-weight: 700; }
.state.soldout { color: var(--red); }
.desc { white-space: pre-wrap; font-size: 14px; line-height: 1.5; color: var(--text); margin: 12px 0 0; }
.stepper {
  display: flex; align-items: center; justify-content: center; gap: 18px;
  height: 48px; border-radius: 15px; background: var(--surface2); margin-top: 16px;
}
.stepper button {
  width: 44px; height: 40px; border: 0; border-radius: 12px; background: var(--surface);
  color: var(--text); font-size: 20px; font-weight: 800; cursor: pointer;
}
.stepper button:disabled { opacity: 0.35; }
.stepper b { font-size: 16px; min-width: 20px; text-align: center; }
.go-cart { margin-top: 10px; height: 44px; }
.error { text-align: center; color: var(--red); margin-top: 40px; }
</style>
