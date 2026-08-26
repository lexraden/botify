<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchProductReviews, fetchShop, trackEvent } from '../api'
import { t, intlLocale } from '../i18n'
import BrandBadge from '../components/BrandBadge.vue'
import { useCartStore } from '../stores/cart'

const route = useRoute()
const router = useRouter()
const cart = useCartStore()
const product = ref(null)
const reviews = ref([])
const error = ref('')

const fmtDate = (iso) =>
  new Date(iso).toLocaleDateString(intlLocale(), { day: 'numeric', month: 'long' })

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
      error.value = t('product.notFound')
      return
    }
    trackEvent('product_view', product.value.id)
    // отзывы — украшение: не загрузились, товар всё равно работает
    fetchProductReviews(product.value.id).then((r) => (reviews.value = r)).catch(() => {})
  } catch (e) {
    error.value = e.response?.data?.detail || t('product.loadError')
  }
})
</script>

<template>
  <div class="detail">
    <a class="back" @click="router.push('/')">← {{ t('common.toCatalog') }}</a>

    <template v-if="product">
      <div class="photo">
        <img v-if="product.image_url" :src="product.image_url" :alt="product.title" />
        <span v-else>{{ emoji }}</span>
      </div>

      <h2>{{ product.title }}</h2>
      <div class="price-line">
        <b class="price">{{ Number(product.price) }} USDT</b>
        <span v-if="product.reviews_count" class="state rating">
          ★ {{ Number(product.avg_rating).toFixed(1) }} · {{ product.reviews_count }}
        </span>
        <span v-if="soldOut" class="state soldout">{{ t('product.soldOut') }}</span>
        <span v-else-if="product.stock != null" class="state">{{ t('product.left', { n: product.stock }) }}</span>
      </div>

      <p v-if="product.description" class="desc">{{ product.description }}</p>

      <section v-if="reviews.length" class="reviews">
        <h3>{{ t('product.reviews') }}</h3>
        <!-- вместо личности — случайный псевдоним, сервис анонимный -->
        <div v-for="r in reviews" :key="r.created_at + String(r.rating)" class="review">
          <p v-if="r.author_name" class="author">{{ r.author_name }}</p>
          <div class="review-head">
            <span class="stars">{{ '★'.repeat(r.rating) }}</span>
            <span class="date">{{ fmtDate(r.created_at) }}</span>
          </div>
          <p v-if="r.body">{{ r.body }}</p>
          <div v-if="r.reply_body" class="reply">
            <b>{{ t('product.sellerReply') }}</b>
            <p>{{ r.reply_body }}</p>
          </div>
        </div>
      </section>

      <div v-if="qty" class="stepper">
        <button @click="cart.remove(product)">−</button>
        <b>{{ qty }}</b>
        <button :disabled="maxed" @click="cart.add(product)">+</button>
      </div>
      <button
        v-else-if="!soldOut"
        class="btn btn-primary add-cart"
        @click="cart.add(product)"
      >
        {{ t('product.addToCart') }}
      </button>
      <button v-else class="btn btn-soft" disabled>{{ t('product.soldOut') }}</button>

      <button v-if="cart.count" class="btn btn-green go-cart" @click="router.push('/checkout')">
        {{ t('product.goCart', { n: cart.count, sum: cart.total.toFixed(2) }) }}
      </button>
      <BrandBadge />
    </template>

    <p v-else-if="error" class="error">{{ error }}</p>
  </div>
</template>

<style scoped>
.detail { padding: 18px 16px 24px; }
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
.state.rating { color: #f59e1b; }
.desc { white-space: pre-wrap; font-size: 14px; line-height: 1.5; color: var(--text); margin: 12px 0 0; }
.reviews { margin-top: 18px; display: flex; flex-direction: column; gap: 10px; }
.reviews h3 { font-size: 15px; margin: 0 0 2px; }
.review {
  border: 1px solid var(--border); border-radius: 12px; padding: 10px 12px;
  background: var(--surface);
}
.review-head { display: flex; justify-content: space-between; align-items: baseline; }
.stars { color: #f59e1b; letter-spacing: 1.5px; font-size: 13px; }
.date { color: var(--sub); font-size: 11.5px; font-weight: 700; }
.author { margin: 0 0 4px; font-size: 12px; font-weight: 700; color: var(--text); }
.review p { margin: 5px 0 0; font-size: 13.5px; line-height: 1.45; }
.reply {
  margin-top: 8px;
  border-radius: 10px;
  background: var(--accent-soft);
  padding: 8px 10px;
}
.reply b { font-size: 11.5px; color: var(--accent); }
.reply p { margin: 3px 0 0; font-size: 13px; }
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
.add-cart { margin-top: 20px; }
.go-cart { margin-top: 10px; height: 44px; }
.error { text-align: center; color: var(--red); margin-top: 40px; }
</style>
