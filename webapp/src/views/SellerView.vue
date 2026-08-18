<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { deleteProduct, fetchMe, fetchProducts, fetchSellerOrders, fulfillOrder } from '../api'

const router = useRouter()
const me = ref(null)
const products = ref([])
const orders = ref([])
const error = ref('')
const tab = ref('products')

const STATUS = {
  pending_payment: '⏳ Ожидает оплаты',
  paid: '✅ Оплачен — пора отправлять',
  fulfilled: '📦 Отправлен',
  delivered: '🎉 Доставлен',
  cancelled: '✖️ Отменён',
}

async function reload() {
  ;[me.value, products.value, orders.value] = await Promise.all([
    fetchMe(),
    fetchProducts(),
    fetchSellerOrders(),
  ])
}

onMounted(async () => {
  try {
    await reload()
  } catch (e) {
    error.value = e.response?.data?.detail || 'Ошибка загрузки. Открой приложение из бота.'
  }
})

async function removeProduct(p) {
  await deleteProduct(p.id)
  await reload()
}

const fulfillForm = ref({ orderId: null, tracking: '', url: '', note: '', sending: false })

function openFulfill(o) {
  fulfillForm.value = { orderId: o.id, tracking: '', url: '', note: '', sending: false }
}

async function submitFulfill() {
  const f = fulfillForm.value
  if (f.sending || !(f.tracking || f.url || f.note)) return
  f.sending = true
  try {
    await fulfillOrder(f.orderId, {
      tracking: f.tracking || null,
      url: f.url || null,
      note: f.note || null,
    })
    fulfillForm.value.orderId = null
    await reload()
  } finally {
    f.sending = false
  }
}
</script>

<template>
  <div class="seller">
    <p v-if="error" class="error">{{ error }}</p>
    <template v-else-if="me">
      <h2>Кабинет продавца</h2>

      <div class="stats">
        <div class="stat"><b>{{ me.customers_count }}</b><span>покупателей</span></div>
        <div class="stat"><b>{{ me.orders_count }}</b><span>заказов</span></div>
        <div class="stat"><b>{{ Number(me.commission_pct) }}%</b><span>комиссия</span></div>
      </div>

      <p v-if="!me.bots.length" class="warn">
        ⚠️ Бот ещё не подключён — вернись в чат и пройди настройку через /start.
      </p>

      <nav>
        <button :class="{ active: tab === 'products' }" @click="tab = 'products'">Товары</button>
        <button :class="{ active: tab === 'orders' }" @click="tab = 'orders'">Заказы</button>
      </nav>

      <template v-if="tab === 'products'">
        <button class="add-product" @click="router.push('/seller/product')">+ Добавить товар или услугу</button>
        <div v-for="p in products" :key="p.id" class="row" :class="{ inactive: !p.is_active }">
          <div class="info">
            <b>{{ p.title }}</b>
            <span>{{ Number(p.price) }} USDT · {{ { physical: 'товар', digital: 'digital', service: 'услуга' }[p.type] }}<template v-if="!p.is_active"> · скрыт</template></span>
          </div>
          <div class="row-actions">
            <button @click="router.push(`/seller/product/${p.id}`)">✏️</button>
            <button @click="removeProduct(p)">🗑</button>
          </div>
        </div>
        <p v-if="!products.length" class="empty">Товаров пока нет.</p>
      </template>

      <template v-else>
        <div v-for="o in orders" :key="o.id" class="row order">
          <div class="info">
            <b>Заказ #{{ o.id }} · {{ Number(o.total).toFixed(2) }} {{ o.currency }}</b>
            <span>{{ STATUS[o.status] || o.status }} · {{ o.customer_username ? '@' + o.customer_username : o.customer_first_name || 'аноним' }}</span>
            <span v-if="o.comment" class="comment">💬 {{ o.comment }}</span>

            <button v-if="o.status === 'paid' && fulfillForm.orderId !== o.id" class="fulfill-btn" @click="openFulfill(o)">
              📦 Отправить покупателю
            </button>
            <div v-if="fulfillForm.orderId === o.id" class="fulfill-form">
              <input v-model="fulfillForm.tracking" placeholder="Трек-номер" />
              <input v-model="fulfillForm.url" placeholder="Ссылка (файл / инвайт)" />
              <input v-model="fulfillForm.note" placeholder="Примечание / координаты" />
              <div class="fulfill-actions">
                <button class="cancel" @click="fulfillForm.orderId = null">Отмена</button>
                <button
                  class="send"
                  :disabled="fulfillForm.sending || !(fulfillForm.tracking || fulfillForm.url || fulfillForm.note)"
                  @click="submitFulfill"
                >{{ fulfillForm.sending ? '…' : 'Отправить' }}</button>
              </div>
            </div>
          </div>
        </div>
        <p v-if="!orders.length" class="empty">Заказов пока нет.</p>
      </template>
    </template>
    <p v-else class="empty">Загрузка…</p>
  </div>
</template>

<style scoped lang="scss">
.seller { padding: 16px; }
h2 { margin: 4px 0 12px; }
.stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-bottom: 12px;
  .stat {
    background: var(--tg-theme-secondary-bg-color, #f5f5f5);
    border-radius: 12px;
    padding: 10px;
    text-align: center;
    b { display: block; font-size: 20px; }
    span { font-size: 12px; opacity: 0.7; }
  }
}
.warn {
  background: #fff3cd;
  color: #664d03;
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 14px;
}
nav {
  display: flex;
  gap: 8px;
  margin: 12px 0;
  button {
    flex: 1;
    border: 0;
    border-radius: 10px;
    padding: 10px;
    background: var(--tg-theme-secondary-bg-color, #f0f0f0);
    color: inherit;
    font-weight: 600;
    cursor: pointer;
    &.active { background: var(--tg-theme-button-color, #2481cc); color: var(--tg-theme-button-text-color, #fff); }
  }
}
.add-product {
  width: 100%;
  border: 2px dashed var(--tg-theme-button-color, #2481cc);
  background: none;
  color: var(--tg-theme-button-color, #2481cc);
  border-radius: 12px;
  padding: 12px;
  font-weight: 600;
  cursor: pointer;
  margin-bottom: 10px;
}
.row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid var(--tg-theme-secondary-bg-color, #eee);
  &.inactive { opacity: 0.5; }
  .info { display: flex; flex-direction: column; gap: 2px; span { font-size: 13px; opacity: 0.7; } .comment { opacity: 1; } }
  .row-actions button { border: 0; background: none; font-size: 18px; cursor: pointer; }
}
.empty { text-align: center; opacity: 0.6; margin-top: 24px; }
.error { text-align: center; color: #e74c3c; margin-top: 40px; }
.fulfill-btn {
  margin-top: 6px;
  border: 0;
  border-radius: 8px;
  padding: 8px;
  background: #2ecc71;
  color: #fff;
  font-weight: 600;
  cursor: pointer;
}
.fulfill-form {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 8px;
  input {
    border: 1px solid var(--tg-theme-secondary-bg-color, #ddd);
    border-radius: 8px;
    padding: 8px;
    background: var(--tg-theme-bg-color, #fff);
    color: inherit;
    font: inherit;
  }
  .fulfill-actions {
    display: flex;
    gap: 6px;
    button {
      flex: 1;
      border: 0;
      border-radius: 8px;
      padding: 8px;
      font-weight: 600;
      cursor: pointer;
      &.send { background: #2ecc71; color: #fff; &:disabled { opacity: 0.5; } }
      &.cancel { background: var(--tg-theme-secondary-bg-color, #f0f0f0); color: inherit; }
    }
  }
}
</style>
