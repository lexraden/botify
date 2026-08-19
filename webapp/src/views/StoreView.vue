<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { fetchShop } from '../api'
import ProductCard from '../components/ProductCard.vue'
import { useCartStore } from '../stores/cart'

const router = useRouter()
const cart = useCartStore()
const shop = ref(null)
const error = ref('')

onMounted(async () => {
  try {
    shop.value = await fetchShop()
  } catch (e) {
    error.value = e.response?.data?.detail || 'Не удалось загрузить магазин'
  }
})
</script>

<template>
  <div class="store">
    <p v-if="error" class="error">{{ error }}</p>
    <template v-else-if="shop">
      <header>
        <h2>{{ shop.shop_name }}</h2>
        <a class="orders-link" @click="router.push('/my-orders')">Мои покупки</a>
      </header>
      <p v-if="!shop.products.length" class="empty">В этом магазине пока нет товаров.</p>
      <div class="grid">
        <ProductCard v-for="p in shop.products" :key="p.id" :product="p" />
      </div>
      <button v-if="cart.count" class="view-order" @click="router.push('/checkout')">
        VIEW ORDER · {{ cart.total.toFixed(2) }} USDT
      </button>
    </template>
    <p v-else class="empty">Загрузка…</p>
  </div>
</template>

<style scoped lang="scss">
.store { padding: 12px 12px 84px; }
header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  h2 { margin: 4px 0 12px; }
  .orders-link { color: var(--tg-theme-link-color, #2481cc); cursor: pointer; font-size: 14px; }
}
.grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  @media (max-width: 340px) { grid-template-columns: repeat(2, 1fr); }
}
.empty { text-align: center; opacity: 0.6; margin-top: 40px; }
.error { text-align: center; color: #e74c3c; margin-top: 40px; }
.view-order {
  position: fixed;
  left: 0; right: 0; bottom: 0;
  border: 0;
  background: #2ecc71;
  color: #fff;
  font-size: 16px;
  font-weight: 700;
  padding: 16px;
  cursor: pointer;
}
</style>
