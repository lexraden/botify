<script setup>
import { computed } from 'vue'
import { useCartStore } from '../stores/cart'

const props = defineProps({ product: { type: Object, required: true } })
const cart = useCartStore()
const qty = computed(() => cart.qtyOf(props.product.id))
const emoji = computed(
  () => ({ physical: '📦', digital: '📕', service: '🛎' })[props.product.type] ?? '📦',
)
</script>

<template>
  <div class="card product">
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
      <button class="minus" @click="cart.remove(product)">−</button>
      <button class="plus" @click="cart.add(product)">+</button>
    </div>
    <button v-else class="add" @click="cart.add(product)">В корзину</button>
  </div>
</template>

<style scoped>
.product { position: relative; display: flex; flex-direction: column; gap: 10px; padding: 14px; }
.badge {
  position: absolute; top: 10px; right: 10px; background: var(--accent); color: #fff;
  border-radius: 11px; min-width: 22px; height: 22px; display: flex; align-items: center;
  justify-content: center; font-size: 12px; font-weight: 800;
}
.image {
  height: 72px; border-radius: 14px; background: var(--surface2);
  display: flex; align-items: center; justify-content: center; font-size: 46px;
}
.image img { max-height: 72px; max-width: 100%; border-radius: 12px; }
.meta { display: flex; flex-direction: column; gap: 2px; }
.title { font-size: 14px; font-weight: 700; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.price { font-size: 15px; font-weight: 800; }
.add, .stepper button {
  border: 0; border-radius: 12px; height: 40px; font-size: 14px; font-weight: 800; cursor: pointer;
}
.add { background: var(--accent-soft); color: var(--accent); width: 100%; }
.stepper { display: flex; gap: 8px; }
.stepper button { flex: 1; font-size: 20px; }
.stepper .minus { background: var(--surface2); color: var(--text); }
.stepper .plus { background: var(--accent); color: #fff; }
</style>
