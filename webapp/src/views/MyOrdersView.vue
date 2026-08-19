<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchMyOrders } from '../api'

const route = useRoute()
const router = useRouter()
const orders = ref(null)

const STATUS = {
  pending_payment: '⏳ Ожидает оплаты',
  paid: '✅ Оплачен',
  fulfilled: '📦 Отправлен',
  delivered: '🎉 Доставлен',
  cancelled: '✖️ Отменён',
}

onMounted(async () => {
  orders.value = await fetchMyOrders()
})
</script>

<template>
  <div class="orders">
    <header>
      <h2>Мои покупки</h2>
      <a @click="router.push('/')">В каталог</a>
    </header>
    <p v-if="route.query.created" class="notice">
      Заказ #{{ route.query.created }} создан.
      <template v-if="route.query.pay === '1'">
        Заверши оплату в открывшемся окне @CryptoBot — после оплаты придёт подтверждение в чат
        с ботом.
      </template>
      <template v-else>Оплата временно недоступна — попробуй позже.</template>
    </p>
    <p v-if="orders && !orders.length" class="empty">Покупок пока нет.</p>
    <div v-for="o in orders" :key="o.id" class="order">
      <div class="head">
        <b>Заказ #{{ o.id }}</b>
        <span>{{ STATUS[o.status] || o.status }}</span>
      </div>
      <div v-for="i in o.items" :key="i.product_id" class="item">
        {{ i.title }} × {{ i.qty }} — {{ (Number(i.price) * i.qty).toFixed(2) }} USDT
      </div>
      <div class="total">Итого: {{ Number(o.total).toFixed(2) }} {{ o.currency }}</div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.orders { padding: 16px; }
header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  a { color: var(--accent); cursor: pointer; font-size: 14px; }
}
.notice {
  background: var(--accent-soft);
  border-radius: 11px;
  padding: 10px 12px;
  font-size: 13px;
}
.empty { text-align: center; opacity: 0.6; margin-top: 40px; }
.order {
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 12px;
  margin-bottom: 10px;
  .head { display: flex; justify-content: space-between; margin-bottom: 6px; }
  .item { font-size: 13px; padding: 2px 0; }
  .total { margin-top: 6px; font-weight: 700; }
}
</style>
