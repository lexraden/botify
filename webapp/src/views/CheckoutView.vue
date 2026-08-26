<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { createOrder, trackEvent } from '../api'
import { t } from '../i18n'
import { useCartStore } from '../stores/cart'
import { apiError } from '../services/apiError'

const router = useRouter()
const cart = useCartStore()
const comment = ref('')
const submitting = ref(false)
const error = ref('')

// Физический товар нужно куда-то везти. У цифровых заказов адрес не спрашиваем:
// лишние поля в чекауте стоят конверсии, а продавцу они там не нужны.
const needsDelivery = computed(() =>
  Object.values(cart.items).some((i) => i.product.type === 'physical'),
)
const delivery = ref({ name: '', phone: '', address: '' })
const deliveryReady = computed(
  () =>
    !needsDelivery.value ||
    (delivery.value.name.trim() && delivery.value.phone.trim() && delivery.value.address.trim()),
)

onMounted(() => trackEvent('checkout_start'))

async function pay() {
  if (!cart.count || submitting.value) return
  if (!deliveryReady.value) {
    error.value = t('checkout.deliveryRequired')
    return
  }
  submitting.value = true
  error.value = ''
  try {
    const order = await createOrder(
      cart.asOrderItems,
      comment.value || null,
      needsDelivery.value
        ? {
            name: delivery.value.name.trim(),
            phone: delivery.value.phone.trim(),
            address: delivery.value.address.trim(),
          }
        : null,
    )
    cart.clear()
    if (order.payment_url) {
      const tg = window.Telegram?.WebApp
      if (tg?.openTelegramLink) tg.openTelegramLink(order.payment_url)
      else window.open(order.payment_url, '_blank')
    }
    router.push({ name: 'my-orders', query: { created: order.id, pay: order.payment_url ? 1 : 0 } })
  } catch (e) {
    error.value = apiError(e, 'checkout.error')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="checkout">
    <header>
      <h2>{{ t('checkout.title') }}</h2>
      <a class="edit" @click="router.push('/')">{{ t('checkout.edit') }}</a>
    </header>

    <div v-for="entry in Object.values(cart.items)" :key="entry.product.id" class="row">
      <div class="info">
        <b>{{ entry.product.title }}</b>
        <span class="qty">{{ entry.qty }}x</span>
      </div>
      <div class="price">{{ (Number(entry.product.price) * entry.qty).toFixed(2) }} USDT</div>
    </div>

    <p v-if="!cart.count" class="empty">{{ t('checkout.empty') }} <a @click="router.push('/')">{{ t('common.toCatalog') }}</a></p>

    <section v-if="needsDelivery" class="delivery">
      <h3>{{ t('checkout.deliveryTitle') }}</h3>
      <p class="hint">{{ t('checkout.deliveryHint') }}</p>
      <input v-model="delivery.name" :placeholder="t('checkout.namePh')" :maxlength="128" />
      <input
        v-model="delivery.phone"
        type="tel"
        inputmode="tel"
        :placeholder="t('checkout.phonePh')"
        :maxlength="32"
      />
      <textarea
        v-model="delivery.address"
        :placeholder="t('checkout.addressPh')"
        :maxlength="512"
        rows="2"
      />
    </section>

    <textarea v-model="comment" :placeholder="t('checkout.commentPh')" rows="3" />

    <p v-if="error" class="error">{{ error }}</p>

    <button class="pay" :disabled="!cart.count || submitting || !deliveryReady" @click="pay">
      {{ submitting ? '…' : t('checkout.pay', { sum: cart.total.toFixed(2) }) }}
    </button>
  </div>
</template>

<style scoped lang="scss">
.checkout { padding: 16px 16px 80px; }
header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  h2 { margin: 0 0 14px; font-size: 17px; letter-spacing: 0.3px; }
  .edit { color: var(--green); cursor: pointer; }
}
.row {
  display: flex;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px solid var(--surface2);
  .qty { color: #f5a623; font-weight: 700; margin-left: 8px; }
}
.delivery {
  margin-top: 18px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  h3 { margin: 0; font-size: 15px; }
  .hint { margin: -4px 0 2px; font-size: 13px; color: var(--sub); }
  input {
    width: 100%;
    box-sizing: border-box;
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 10px;
    background: var(--surface);
    color: inherit;
    font: inherit;
  }
  textarea { margin-top: 0; }
}
textarea {
  width: 100%;
  box-sizing: border-box;
  margin-top: 16px;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 10px;
  background: var(--surface);
  color: inherit;
  font: inherit;
  resize: none;
}
.empty { text-align: center; opacity: 0.7; a { color: var(--accent); cursor: pointer; } }
.error { color: var(--red); }
.pay {
  position: fixed;
  left: 0; right: 0; bottom: 0;
  z-index: 20; /* поверх плашки «Сделано через Botify» */
  border: 0;
  background: var(--green);
  color: #fff;
  font-size: 15px;
  font-weight: 700;
  padding: 15px;
  cursor: pointer;
  &:disabled { opacity: 0.5; }
}
</style>
