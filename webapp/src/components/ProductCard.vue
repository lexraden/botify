<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
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
const qty = computed(() => cart.qtyOf(props.product.id))
const emoji = computed(
  () => ({ physical: '📦', digital: '📕', service: '🛎' })[props.product.type] ?? '📦',
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
      <div class="price">{{ Number(product.price) }} USDT</div>
    </div>
    <div v-if="qty" class="stepper">
      <button class="minus" @click.stop="cart.remove(product)">−</button>
      <button class="plus" :disabled="maxed" @click.stop="cart.add(product)">+</button>
    </div>
    <button v-else-if="!soldOut" class="add" @click.stop="cart.add(product)">В корзину</button>
    <button v-else class="add soldout" disabled>Нет в наличии</button>
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
.price { font-size: 14px; font-weight: 800; }
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
</style>
