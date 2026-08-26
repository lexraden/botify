<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { fetchShop, trackEvent } from '../api'
import { t } from '../i18n'
import BrandBadge from '../components/BrandBadge.vue'
import ProductCard from '../components/ProductCard.vue'
import { useCartStore } from '../stores/cart'

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

onMounted(async () => {
  try {
    shop.value = await fetchShop()
    // корзина могла пережить закрытие приложения — сверяем её с каталогом:
    // удалённые товары выкидываем, цены и сток обновляем
    cart.syncWithShop(shop.value.products)
    trackEvent('shop_open')
  } catch (e) {
    error.value = e.response?.data?.detail || t('store.error')
  }
})
</script>

<template>
  <div class="store">
    <p v-if="error" class="error">{{ error }}</p>
    <template v-else-if="shop">
      <header>
        <!-- Личность магазина: буква юзернейма + @username. Фото бота из
             Telegram сюда не тянем: Bot API не отдаёт боту его собственную
             аватарку (getChat на себя — chat not found, getMyPhoto нет). -->
        <div class="shop-id">
          <div class="avatar letter">{{ shop.shop_name.charAt(1).toUpperCase() }}</div>
          <b>{{ shop.shop_name }}</b>
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
      <BrandBadge v-if="!cart.count" />

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
.store { padding: 18px 16px 96px; }
header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.shop-id { display: flex; align-items: center; gap: 10px; min-width: 0; }
.shop-id b { font-size: 16px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.avatar {
  width: 40px; height: 40px; border-radius: 13px; flex-shrink: 0;
  background: var(--accent); color: #fff;
  display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 17px;
}
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
