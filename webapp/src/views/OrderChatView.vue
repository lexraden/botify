<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import OrderChat from '../components/OrderChat.vue'

const route = useRoute()
const router = useRouter()
const botId = computed(() => route.params.botId)
const orderId = computed(() => route.params.orderId)
</script>

<template>
  <div class="order-chat-view">
    <a
      class="back"
      @click="router.push({ path: `/shop/${botId}`, query: { tab: 'orders' } })"
    >← К заказам</a>
    <h2>Заказ #{{ orderId }} · Чат</h2>
    <p class="sub">Покупатель анонимен: переписка привязана к заказу, а не к личности.</p>

    <OrderChat :bot-id="botId" :order-id="orderId" />
  </div>
</template>

<style scoped>
.order-chat-view { padding: 18px 16px 36px; }
.back {
  display: inline-block; margin-bottom: 14px;
  color: var(--sub); font-size: 14px; font-weight: 700; cursor: pointer;
}
h2 { font-size: 18px; margin: 0 0 4px; }
.sub { font-size: 12px; color: var(--sub); margin: 0 0 14px; }
</style>
