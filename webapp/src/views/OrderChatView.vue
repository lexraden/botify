<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { t } from '../i18n'
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
    >{{ t('chat.back') }}</a>
    <h2>{{ t('chat.title', { n: orderId }) }}</h2>
    <p class="sub">{{ t('chat.anonymousSub') }}</p>

    <OrderChat :bot-id="botId" :order-id="orderId" />
  </div>
</template>

<style scoped>
/* Экран во всю высоту, чат растягивается и прижимает композер к низу */
.order-chat-view {
  padding: 18px 16px calc(16px + env(safe-area-inset-bottom));
  min-height: 100dvh; box-sizing: border-box;
  display: flex; flex-direction: column;
}
.order-chat-view .back, .order-chat-view h2, .order-chat-view .sub { flex-shrink: 0; }
.back {
  display: inline-block; margin-bottom: 14px;
  color: var(--sub); font-size: 14px; font-weight: 700; cursor: pointer;
}
h2 { font-size: 18px; margin: 0 0 4px; }
.sub { font-size: 12px; color: var(--sub); margin: 0 0 14px; }
</style>
