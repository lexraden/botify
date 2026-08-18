<script setup>
import { computed } from 'vue'
import { useCartStore } from '../stores/cart'

const props = defineProps({ product: { type: Object, required: true } })
const cart = useCartStore()
const qty = computed(() => cart.qtyOf(props.product.id))
</script>

<template>
  <div class="card">
    <div class="badge" v-if="qty">{{ qty }}</div>
    <div class="img">
      <img v-if="product.image_url" :src="product.image_url" :alt="product.title" />
      <span v-else class="emoji">{{ product.type === 'physical' ? '📦' : product.type === 'digital' ? '📕' : '🛎' }}</span>
    </div>
    <div class="name">{{ product.title }} · <b>{{ Number(product.price) }} USDT</b></div>
    <div class="actions">
      <template v-if="qty">
        <button class="btn minus" @click="cart.remove(product)">−</button>
        <button class="btn plus" @click="cart.add(product)">+</button>
      </template>
      <button v-else class="btn add" @click="cart.add(product)">ADD</button>
    </div>
  </div>
</template>

<style scoped lang="scss">
.card {
  position: relative;
  text-align: center;
  padding: 8px 4px;
}
.badge {
  position: absolute;
  top: 0;
  right: 10px;
  background: var(--tg-theme-button-color, #f5a623);
  color: var(--tg-theme-button-text-color, #fff);
  border-radius: 50%;
  min-width: 22px;
  height: 22px;
  line-height: 22px;
  font-size: 13px;
  font-weight: 700;
}
.img {
  height: 76px;
  display: flex;
  align-items: center;
  justify-content: center;
  img { max-height: 76px; max-width: 100%; border-radius: 8px; }
  .emoji { font-size: 56px; }
}
.name {
  font-size: 13px;
  margin: 6px 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.actions {
  display: flex;
  gap: 6px;
  justify-content: center;
}
.btn {
  border: 0;
  border-radius: 8px;
  padding: 8px 0;
  font-weight: 700;
  color: #fff;
  cursor: pointer;
  flex: 1;
  max-width: 110px;
  &.add { background: #f5a623; }
  &.plus { background: #f5a623; }
  &.minus { background: #e74c3c; }
}
</style>
