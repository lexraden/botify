<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { createOrder } from '../api'
import { useCartStore } from '../stores/cart'

const router = useRouter()
const cart = useCartStore()
const comment = ref('')
const submitting = ref(false)
const error = ref('')

async function pay() {
  if (!cart.count || submitting.value) return
  submitting.value = true
  error.value = ''
  try {
    const order = await createOrder(cart.asOrderItems, comment.value || null)
    cart.clear()
    // Этап 5: здесь появится редирект на оплату Crypto Pay по invoice_url
    router.push({ name: 'my-orders', query: { created: order.id } })
  } catch (e) {
    error.value = e.response?.data?.detail || 'Не удалось оформить заказ'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="checkout">
    <header>
      <h2>YOUR ORDER</h2>
      <a class="edit" @click="router.push('/')">Edit</a>
    </header>

    <div v-for="entry in Object.values(cart.items)" :key="entry.product.id" class="row">
      <div class="info">
        <b>{{ entry.product.title }}</b>
        <span class="qty">{{ entry.qty }}x</span>
      </div>
      <div class="price">{{ (Number(entry.product.price) * entry.qty).toFixed(2) }} USDT</div>
    </div>

    <p v-if="!cart.count" class="empty">Корзина пуста. <a @click="router.push('/')">В каталог</a></p>

    <textarea v-model="comment" placeholder="Комментарий к заказу — детали, пожелания…" rows="3" />

    <p v-if="error" class="error">{{ error }}</p>

    <button class="pay" :disabled="!cart.count || submitting" @click="pay">
      {{ submitting ? '…' : `PAY ${cart.total.toFixed(2)} USDT` }}
    </button>
  </div>
</template>

<style scoped lang="scss">
.checkout { padding: 16px 16px 84px; }
header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  h2 { margin: 0 0 16px; font-size: 18px; letter-spacing: 0.5px; }
  .edit { color: #2ecc71; cursor: pointer; }
}
.row {
  display: flex;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px solid var(--tg-theme-secondary-bg-color, #f0f0f0);
  .qty { color: #f5a623; font-weight: 700; margin-left: 8px; }
}
textarea {
  width: 100%;
  box-sizing: border-box;
  margin-top: 16px;
  border: 1px solid var(--tg-theme-secondary-bg-color, #ddd);
  border-radius: 10px;
  padding: 10px;
  background: var(--tg-theme-bg-color, #fff);
  color: inherit;
  font: inherit;
  resize: none;
}
.empty { text-align: center; opacity: 0.7; a { color: var(--tg-theme-link-color, #2481cc); cursor: pointer; } }
.error { color: #e74c3c; }
.pay {
  position: fixed;
  left: 0; right: 0; bottom: 0;
  border: 0;
  background: #2ecc71;
  color: #fff;
  font-size: 16px;
  font-weight: 700;
  padding: 16px;
  cursor: pointer;
  &:disabled { opacity: 0.5; }
}
</style>
