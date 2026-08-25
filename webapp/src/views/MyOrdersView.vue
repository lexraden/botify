<script setup>
// Тонкая обёртка: заголовок и notice из query (?created/?pay) после оплаты.
// Сам список покупок — components/BuyerOrders.vue, он же живёт в профиле.
import { useRoute, useRouter } from 'vue-router'
import { t } from '../i18n'
import BrandBadge from '../components/BrandBadge.vue'
import BuyerOrders from '../components/BuyerOrders.vue'

const route = useRoute()
const router = useRouter()
</script>

<template>
  <div class="orders">
    <header>
      <h2>{{ t('orders.title') }}</h2>
      <a @click="router.push('/')">{{ t('common.toCatalog') }}</a>
    </header>
    <p v-if="route.query.created" class="notice">
      {{ t('orders.created', { n: route.query.created }) }}
      <template v-if="route.query.pay === '1'">
        {{ t('orders.payWindow') }}
      </template>
      <template v-else>{{ t('orders.payUnavailable') }}</template>
    </p>
    <BuyerOrders />
    <!-- нижний отступ с запасом под фиксированную плашку «Сделано через Botify» -->
    <BrandBadge />
  </div>
</template>

<style scoped lang="scss">
/* нижний отступ с запасом под фиксированную плашку «Сделано через Botify» */
.orders { padding: 16px 16px 76px; }
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
</style>
