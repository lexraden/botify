<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { fetchShop, trackEvent } from '../api'
import BrandBadge from '../components/BrandBadge.vue'
import ProductCard from '../components/ProductCard.vue'
import { useCartStore } from '../stores/cart'

const router = useRouter()
const cart = useCartStore()
const shop = ref(null)
const error = ref('')

onMounted(async () => {
  try {
    shop.value = await fetchShop()
    // корзина могла пережить закрытие приложения — сверяем её с каталогом:
    // удалённые товары выкидываем, цены и сток обновляем
    cart.syncWithShop(shop.value.products)
    trackEvent('shop_open')
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
        <!-- Имя магазина не показываем: покупатель уже внутри бота этого
             магазина, дублировать @username незачем. Справа — профиль. -->
        <button class="profile-btn" aria-label="Профиль" @click="router.push('/profile')">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="8" r="4" />
            <path d="M4.5 20a7.5 7.5 0 0 1 15 0" />
          </svg>
        </button>
      </header>

      <p v-if="!shop.products.length" class="empty">В этом магазине пока нет товаров.</p>
      <div class="grid">
        <ProductCard v-for="p in shop.products" :key="p.id" :product="p" @seen="trackEvent('product_view', p.id)" />
      </div>
      <!-- при открытой корзине прячем плашку: низ экрана занят панелью корзины -->
      <BrandBadge v-if="!cart.count" />

      <button v-if="cart.count" class="cart-bar" @click="router.push('/checkout')">
        <span class="left">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round">
            <path d="M6 7h12l-1.2 12.2a2 2 0 0 1-2 1.8H9.2a2 2 0 0 1-2-1.8L6 7z" />
            <path d="M9 7V6a3 3 0 0 1 6 0v1" />
          </svg>
          Корзина · {{ cart.count }}
        </span>
        <span>{{ cart.total.toFixed(2) }} USDT</span>
      </button>
    </template>
  </div>
</template>

<style scoped>
.store { padding: 18px 16px 96px; }
header { display: flex; justify-content: flex-end; margin-bottom: 16px; }
.profile-btn {
  width: 38px; height: 38px; border-radius: 13px; border: 0; background: var(--surface2);
  color: var(--text); display: flex; align-items: center; justify-content: center; cursor: pointer;
}
.grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.empty { text-align: center; color: var(--sub); margin-top: 40px; }
.error { text-align: center; color: var(--red); margin-top: 40px; }
.cart-bar {
  position: fixed; left: 16px; right: 16px; bottom: 18px; height: 56px; border: 0;
  border-radius: 18px; background: var(--green); color: var(--on-green); box-shadow: var(--shadow);
  display: flex; align-items: center; justify-content: space-between; padding: 0 20px;
  font-size: 15px; font-weight: 800; cursor: pointer;
}
.cart-bar .left { display: flex; align-items: center; gap: 10px; }
</style>
