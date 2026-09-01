<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchProductReviews, fetchShop, trackEvent } from '../api'
import { t, intlLocale } from '../i18n'
import { useCartStore } from '../stores/cart'
import { apiError } from '../services/apiError'

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
// --- вариации ---
// Пусто — товар покупается сам. Иначе покупать можно только выбранную
// вариацию: цена, остаток и фото у неё свои, а price/stock самого товара —
// витринные («от 500» и сумма остатков).
const variants = computed(() => product.value?.variants || [])
const chosen = ref(null)
const hasVariants = computed(() => variants.value.length > 0)

// первая, у которой что-то осталось — покупателю не нужно тыкать в
// распроданные, чтобы найти доступную
function pickDefault() {
  const list = variants.value
  chosen.value = list.find((v) => v.stock == null || v.stock > 0) || list[0] || null
}

// цена и остаток берутся у вариации, если она есть
const shown = computed(() => chosen.value ?? product.value)
// Название и описание выбранной вариации, если она их задала. Пусто —
// товарные: у вариаций, созданных до появления этих полей, их нет вовсе
const title = computed(() => chosen.value?.title || product.value?.title || '')
const description = computed(
  () => chosen.value?.description || product.value?.description || '',
)
const price = computed(() => Number(shown.value?.price ?? 0))
// Скидка живёт там же, где цена: у вариации — своя, у товара без вариаций —
// его собственная. shown уже указывает на нужную из двух.
const comparePrice = computed(() => {
  const value = shown.value?.compare_at_price
  return value == null ? null : Number(value)
})
const gallery = computed(() => {
  const own = chosen.value?.images
  if (own?.length) return own
  return product.value?.image_url ? [product.value.image_url] : []
})

const soldOut = computed(() => shown.value?.stock === 0)
// Точный склад покупателю ни к чему: это шум, да и оборот магазина наружу.
// Малый остаток показываем числом — это правда и повод поторопиться.
const LOW_STOCK = 10
const stockLine = computed(() => {
  const left = shown.value?.stock
  return left != null && left <= LOW_STOCK
    ? t('product.left', { n: left })
    : t('product.inStock')
})
const qty = computed(() =>
  product.value ? cart.qtyOf(product.value.id, chosen.value?.id ?? null) : 0,
)
const maxed = computed(() => shown.value?.stock != null && qty.value >= shown.value.stock)

function addToCart() {
  if (product.value) cart.add(product.value, chosen.value)
}
function removeFromCart() {
  if (product.value) cart.remove(product.value, chosen.value)
}

function variantLabel(v) {
  const filled = Object.values(v.attributes || {})
    .map((x) => String(x).trim())
    .filter(Boolean)
  return filled.length ? filled.join(' · ') : t('product.variantFallback')
}

onMounted(async () => {
  try {
    const shop = await fetchShop()
    product.value = shop.products.find((p) => p.id === Number(route.params.id)) || null
    if (!product.value) {
      error.value = t('product.notFound')
      return
    }
    pickDefault()
    trackEvent('product_view', product.value.id)
    // отзывы — украшение: не загрузились, товар всё равно работает
    fetchProductReviews(product.value.id).then((r) => (reviews.value = r)).catch(() => {})
  } catch (e) {
    error.value = apiError(e, 'product.loadError')
  }
})
</script>

<template>
  <div class="detail">
    <a class="back" @click="router.push('/')">← {{ t('common.toCatalog') }}</a>

    <template v-if="product">
      <!-- галерея: фото выбранной вариации, иначе одно фото товара -->
      <div class="photo">
        <img v-if="gallery.length" :src="gallery[0]" :alt="title" />
        <span v-else>{{ emoji }}</span>
      </div>
      <div v-if="gallery.length > 1" class="strip">
        <img v-for="(url, i) in gallery.slice(1)" :key="url + i" :src="url" alt="" />
      </div>

      <h2>{{ title }}</h2>
      <div class="price-line">
        <b class="price">{{ price }} USDT</b>
        <s v-if="comparePrice" class="was">{{ comparePrice }} USDT</s>
        <span v-if="product.reviews_count" class="state rating">
          ★ {{ Number(product.avg_rating).toFixed(1) }} · {{ product.reviews_count }}
        </span>
        <span v-if="soldOut" class="state soldout">{{ t('product.soldOut') }}</span>
        <span v-else-if="shown.stock != null" class="state">{{ stockLine }}</span>
      </div>

      <!-- Выбор вариации. Без него покупатель не смог бы купить то, что
           продавец завёл: платят всегда за конкретную вариацию. -->
      <div v-if="hasVariants" class="variants">
        <button
          v-for="v in variants"
          :key="v.id"
          type="button"
          class="chip"
          :class="{ active: chosen?.id === v.id, out: v.stock === 0 }"
          :disabled="v.stock === 0"
          @click="chosen = v"
        >
          {{ variantLabel(v) }}
          <span v-if="v.stock === 0" class="chip-note">{{ t('product.soldOut') }}</span>
        </button>
      </div>

      <p v-if="description" class="desc">{{ description }}</p>

      <section v-if="reviews.length" class="reviews">
        <h3>{{ t('product.reviews') }}</h3>
        <!-- подпись: имя из Telegram; у безымянных профилей — псевдоним -->
        <div v-for="r in reviews" :key="r.created_at + String(r.rating)" class="review">
          <!-- шапка отзыва: имя слева, дата здесь же; звёзды — строкой ниже -->
          <div class="review-head">
            <span v-if="r.author_name" class="author">{{ r.author_name }}</span>
            <span class="date">{{ fmtDate(r.created_at) }}</span>
          </div>
          <span class="stars">{{ '★'.repeat(r.rating) }}</span>
          <p v-if="r.body">{{ r.body }}</p>
          <div v-if="r.reply_body" class="reply">
            <b>{{ t('product.sellerReply') }}</b>
            <p>{{ r.reply_body }}</p>
          </div>
        </div>
      </section>

      <!-- покупка закреплена у нижнего края и живёт в два этажа:
           сверху — этот товар (добавить или количество), снизу — «В корзину»,
           пока корзина непуста (хоть с этого товара, хоть с другого) -->
      <div class="buy-bar">
        <div v-if="!soldOut && qty" class="stepper">
          <button @click="removeFromCart">−</button>
          <b>{{ qty }}</b>
          <button :disabled="maxed" @click="addToCart">+</button>
        </div>
        <button v-else-if="!soldOut" class="btn btn-primary" @click="addToCart">
          {{ t('product.addToCart') }}
        </button>
        <button v-else class="btn btn-soft" disabled>{{ t('product.soldOut') }}</button>
        <button v-if="cart.count" class="btn btn-green" @click="router.push('/checkout')">
          {{ t('product.goCart', { n: cart.count, sum: cart.total.toFixed(2) }) }}
        </button>
      </div>
    </template>

    <p v-else-if="error" class="error">{{ error }}</p>
  </div>
</template>

<style scoped>
/* снизу запас под двухэтажную фиксированную панель покупки */
.detail { padding: 18px 16px 148px; }
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
.review-head {
  display: flex; justify-content: space-between; align-items: baseline; gap: 8px;
}
.author {
  font-size: 12px; font-weight: 700; color: var(--text);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.stars { display: block; margin-top: 3px; color: #f59e1b; letter-spacing: 1.5px; font-size: 13px; }
.date { color: var(--sub); font-size: 11.5px; font-weight: 700; white-space: nowrap; }
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
  height: 48px; border-radius: 15px; background: var(--surface2);
}
.stepper button {
  width: 44px; height: 40px; border: 0; border-radius: 12px; background: var(--surface);
  color: var(--text); font-size: 20px; font-weight: 800; cursor: pointer;
}
.stepper button:disabled { opacity: 0.35; }
.stepper b { font-size: 16px; min-width: 20px; text-align: center; }
/* панель покупки прижата к низу экрана — как cart-bar в StoreView, но в два этажа */
.buy-bar {
  position: fixed; left: 16px; right: 16px; bottom: 18px; z-index: 20;
  display: flex; flex-direction: column; gap: 10px;
}
.error { text-align: center; color: var(--red); margin-top: 40px; }

.strip { display: flex; gap: 6px; overflow-x: auto; margin-top: 6px; }
.strip img { width: 62px; height: 62px; border-radius: 11px; object-fit: cover; flex: 0 0 auto; }
.was { color: var(--sub); text-decoration: line-through; font-size: 14px; }
.variants { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0 4px; }
.chip {
  border: 1.5px solid var(--line, var(--border)); background: var(--surface2);
  color: var(--text); border-radius: 12px; padding: 8px 12px; font-size: 13px;
  font-weight: 700; cursor: pointer; display: flex; align-items: center; gap: 6px;
}
.chip.active { border-color: var(--accent); background: var(--accent-soft); color: var(--accent); }
.chip.out { opacity: 0.45; cursor: not-allowed; text-decoration: line-through; }
.chip-note { font-size: 10px; font-weight: 600; text-decoration: none; }
</style>
