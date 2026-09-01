<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { t } from '../i18n'
import { useCartStore } from '../stores/cart'

const props = defineProps({ product: { type: Object, required: true } })
const emit = defineEmits(['seen'])
const router = useRouter()

// Просмотром считаем первое реальное появление карточки на экране,
// а не отрисовку списка — иначе метрика раздувается
const root = ref(null)
let observer = null

onMounted(() => {
  if (!root.value || typeof IntersectionObserver === 'undefined') return
  observer = new IntersectionObserver(
    (entries) => {
      if (entries.some((e) => e.isIntersecting)) {
        emit('seen')
        observer?.disconnect()
        observer = null
      }
    },
    { threshold: 0.5 },
  )
  observer.observe(root.value)
})

onUnmounted(() => observer?.disconnect())
const cart = useCartStore()
// У товара с вариациями нельзя купить «товар вообще»: платят за конкретный
// размер. Карточка в сетке места для выбора не имеет, поэтому она ведёт на
// страницу товара — там вариации и выбираются.
const hasVariants = computed(() => (props.product.variants || []).length > 0)
// значок на карточке — сколько всего этого товара в корзине, всеми вариациями
const qty = computed(() =>
  hasVariants.value
    ? Object.values(cart.items)
        .filter((i) => i.product.id === props.product.id)
        .reduce((n, i) => n + i.qty, 0)
    : cart.qtyOf(props.product.id),
)
function openProduct() {
  router.push(`/product/${props.product.id}`)
}
const emoji = computed(
  () => ({ physical: '📦', digital: '📕', service: '🛎' })[props.product.type] ?? '📦',
)
// Зачёркнутая цена помещается в сетке только когда справа не стоит рейтинг:
// цена, старая цена и звёзды в одной строке мелкой карточки читаются кашей.
// Есть отзывы — место занято ими, скидку видно на странице товара.
// У товара с вариациями её нет и там: показанная цена это «от N», собранное
// из разных вариаций, и зачёркивать рядом одно число значило бы соврать.
const discount = computed(() =>
  !hasVariants.value && !props.product.reviews_count && props.product.compare_at_price != null
    ? Number(props.product.compare_at_price)
    : null,
)
// stock: null — не ограничен, 0 — распродано
const soldOut = computed(() => props.product.stock === 0)
const maxed = computed(() => props.product.stock != null && qty.value >= props.product.stock)
</script>

<template>
  <div ref="root" class="card product" @click="router.push(`/product/${product.id}`)">
    <div v-if="qty" class="badge">{{ qty }}</div>
    <div class="image">
      <img v-if="product.image_url" :src="product.image_url" :alt="product.title" />
      <span v-else>{{ emoji }}</span>
    </div>
    <div class="meta">
      <div class="title">{{ product.title }}</div>
      <div class="price-row">
        <div class="price">
          <span v-if="hasVariants" class="from">{{ t('card.from') }}</span>
          {{ Number(product.price) }} USDT
          <s v-if="discount" class="was">{{ discount }} USDT</s>
        </div>
        <div v-if="product.reviews_count" class="rating">
          ★ {{ Number(product.avg_rating).toFixed(1) }} · {{ product.reviews_count }}
        </div>
      </div>
    </div>
    <!-- одна цепочка v-if/v-else-if намеренно: товар в корзине показывает
         только «− +», кнопка «Добавить» под ним не нужна и сбивает счёт -->
    <div v-if="qty && !hasVariants" class="stepper">
      <button class="minus" @click.stop="cart.remove(product)">−</button>
      <button class="plus" :disabled="maxed" @click.stop="cart.add(product)">+</button>
    </div>
    <button
      v-else-if="hasVariants"
      class="add"
      @click.stop="openProduct"
    >{{ t('card.choose') }}</button>
    <button v-else-if="!soldOut" class="add" @click.stop="cart.add(product)">{{ t('card.addToCart') }}</button>
    <button v-else class="add soldout" disabled>{{ t('card.soldOut') }}</button>
  </div>
</template>

<style scoped>
.product { position: relative; display: flex; flex-direction: column; gap: 8px; padding: 12px; }
.badge {
  position: absolute; top: 10px; right: 10px; background: var(--accent); color: #fff;
  border-radius: 11px; min-width: 22px; height: 22px; display: flex; align-items: center;
  justify-content: center; font-size: 12px; font-weight: 800;
}
.image {
  width: 100%; aspect-ratio: 1; border-radius: 14px; background: var(--surface2);
  display: flex; align-items: center; justify-content: center; font-size: 48px;
  overflow: hidden;
}
.image img { width: 100%; height: 100%; object-fit: cover; border-radius: inherit; }
.meta { display: flex; flex-direction: column; gap: 2px; }
.title { font-size: 13px; font-weight: 700; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.price-row { display: flex; align-items: baseline; gap: 8px; }
.price { font-size: 14px; font-weight: 800; }
.was { color: var(--sub); font-weight: 600; font-size: 12px; margin-left: 4px; }
.rating { font-size: 11.5px; font-weight: 700; color: #f59e1b; white-space: nowrap; }
.add, .stepper button {
  border: 0; border-radius: 11px; height: 36px; font-size: 13px; font-weight: 800; cursor: pointer;
}
.add { background: var(--accent-soft); color: var(--accent); width: 100%; }
.stepper { display: flex; gap: 8px; }
.stepper button { flex: 1; font-size: 18px; }
.stepper .minus { background: var(--surface2); color: var(--text); }
.stepper .plus { background: var(--accent); color: #fff; }
.plus:disabled { opacity: 0.35; }
.add.soldout { background: var(--surface2); color: var(--sub); }
.from { color: var(--sub); font-weight: 600; font-size: 11px; }
</style>
