<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { fetchShop, trackEvent } from '../api'
import { t } from '../i18n'
import BrandBadge from '../components/BrandBadge.vue'
import ProductCard from '../components/ProductCard.vue'
import { useCartStore } from '../stores/cart'
import { apiError } from '../services/apiError'

const router = useRouter()
const cart = useCartStore()
const shop = ref(null)
const error = ref('')

// Поиск по каталогу: товары уже загружены целиком, фильтр чисто клиентский
const searchOpen = ref(false)
const query = ref('')
const filtered = computed(() => {
  const products = shop.value?.products ?? []
  const q = query.value.trim().toLowerCase()
  if (!q) return products
  return products.filter(
    (p) =>
      p.title.toLowerCase().includes(q) ||
      (p.description ?? '').toLowerCase().includes(q),
  )
})

function toggleSearch() {
  searchOpen.value = !searchOpen.value
  query.value = ''
}

// без своего лого — аватар из первой буквы названия
const initial = computed(() => (shop.value?.shop_name || '?').charAt(0).toUpperCase())

// «продажа/продажи/продаж»: русский плюрализм по mod10/mod100
const salesWord = computed(() => {
  const n = shop.value?.sales_count ?? 0
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return t('store.salesOne')
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return t('store.salesFew')
  return t('store.salesMany')
})

onMounted(async () => {
  try {
    shop.value = await fetchShop()
    // корзина могла пережить закрытие приложения — сверяем её с каталогом:
    // удалённые товары выкидываем, цены и сток обновляем
    cart.syncWithShop(shop.value.products)
    trackEvent('shop_open')
  } catch (e) {
    error.value = apiError(e, 'store.error')
  }
})
</script>

<template>
  <!-- с открытой корзиной снизу фиксированная панель — держим запас под неё -->
  <div class="store" :class="{ 'has-cart': cart.count }">
    <p v-if="error" class="error">{{ error }}</p>
    <template v-else-if="shop">
      <header>
        <!-- хиро магазина: аватар (лого или буква), имя бренда и trust-строка.
             Имя бэкенд отдаёт с фолбэком @username; у магазина без продаж
             trust-строки нет вовсе, рейтинга нет при отсутствии отзывов -->
        <div class="shop-id">
          <img v-if="shop.logo_url" class="avatar" :src="shop.logo_url" :alt="shop.shop_name" />
          <div v-else class="avatar letter">{{ initial }}</div>
          <div class="titles">
            <h2>{{ shop.shop_name }}</h2>
            <div v-if="shop.sales_count" class="trust">
              <template v-if="shop.rating != null">
                <span class="star">★</span>{{ shop.rating.toFixed(1) }} ·
              </template>
              {{ shop.sales_count }} {{ salesWord }}
            </div>
          </div>
        </div>
        <div class="controls">
          <button
            class="icon-btn"
            :class="{ active: searchOpen }"
            :aria-label="t('store.search')"
            @click="toggleSearch"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="11" cy="11" r="7" />
              <path d="m20 20-3.5-3.5" />
            </svg>
          </button>
          <button class="icon-btn" :aria-label="t('store.profile')" @click="router.push('/profile')">
            <svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="8" r="4" />
              <path d="M4.5 20a7.5 7.5 0 0 1 15 0" />
            </svg>
          </button>
        </div>
      </header>

      <!-- строка поиска раскрывается под шапкой; крестик сбрасывает запрос -->
      <div v-if="searchOpen" class="search-row">
        <input v-model="query" :placeholder="t('store.searchPlaceholder')" type="text" />
        <button v-if="query" class="clear" :aria-label="t('store.clearSearch')" @click="query = ''">✕</button>
      </div>

      <p v-if="!shop.products.length" class="empty">{{ t('store.empty') }}</p>
      <p v-else-if="!filtered.length" class="empty">{{ t('store.nothingFound') }}</p>
      <div class="grid">
        <ProductCard v-for="p in filtered" :key="p.id" :product="p" @seen="trackEvent('product_view', p.id)" />
      </div>
      <!-- при открытой корзине прячем плашку: низ экрана занят панелью корзины -->
      <div v-if="!cart.count" class="badge-spacer"><BrandBadge /></div>

      <button v-if="cart.count" class="cart-bar" @click="router.push('/checkout')">
        <span class="left">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round">
            <path d="M6 7h12l-1.2 12.2a2 2 0 0 1-2 1.8H9.2a2 2 0 0 1-2-1.8L6 7z" />
            <path d="M9 7V6a3 3 0 0 1 6 0v1" />
          </svg>
          {{ t('store.cart', { n: cart.count }) }}
        </span>
        <span>{{ cart.total.toFixed(2) }} USDT</span>
      </button>
    </template>
  </div>
</template>

<style scoped>
.store {
  padding: 18px 16px 24px;
  min-height: 100vh;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
}
/* плашка прижимается к низу экрана, а не липнет к сетке товаров */
.badge-spacer { margin-top: auto; }
.store.has-cart { padding-bottom: 96px; }
header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.shop-id { display: flex; align-items: center; gap: 10px; min-width: 0; }
.avatar { width: 52px; height: 52px; border-radius: 50%; object-fit: cover; flex-shrink: 0; }
.avatar.letter {
  background: var(--accent); color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: 22px; font-weight: 800;
}
.titles { min-width: 0; }
.titles h2 { font-size: 18px; margin: 0 0 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.trust { font-size: 13px; color: var(--sub); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.trust .star { color: var(--orange); margin-right: 3px; }
.controls { display: flex; gap: 8px; flex-shrink: 0; }
.icon-btn {
  width: 42px; height: 42px; border-radius: 13px; border: 0; background: var(--surface2);
  color: var(--text); display: flex; align-items: center; justify-content: center; cursor: pointer;
}
.icon-btn.active { background: var(--accent-soft); color: var(--accent); }
.search-row { position: relative; margin-bottom: 14px; }
.search-row input {
  width: 100%; box-sizing: border-box; height: 44px; border-radius: 13px;
  border: 1px solid var(--line); background: var(--surface2); color: var(--text);
  padding: 0 40px 0 14px; font-size: 15px; outline: none;
}
.search-row input:focus { border-color: var(--accent); }
.search-row .clear {
  position: absolute; right: 6px; top: 0; height: 44px; width: 32px;
  border: 0; background: none; color: var(--sub); font-size: 15px; cursor: pointer;
}
.grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.empty { text-align: center; color: var(--sub); margin-top: 40px; }
.error { text-align: center; color: var(--red); margin-top: 40px; }
.cart-bar {
  position: fixed; left: 16px; right: 16px; bottom: 18px; height: 56px; border: 0; z-index: 20;
  border-radius: 18px; background: var(--green); color: var(--on-green); box-shadow: var(--shadow);
  display: flex; align-items: center; justify-content: space-between; padding: 0 20px;
  font-size: 15px; font-weight: 800; cursor: pointer;
}
.cart-bar .left { display: flex; align-items: center; gap: 10px; }
</style>
