<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  createMailing,
  deleteProduct,
  fetchMailings,
  fetchMe,
  fetchProducts,
  fetchShopOrders,
  fetchShopStats,
  fetchShopSummary,
  fulfillOrder,
} from '../api'

const route = useRoute()
const router = useRouter()
const botId = computed(() => route.params.botId)

const summary = ref(null)
const stats = ref(null)
const products = ref([])
const orders = ref([])
const mailings = ref([])
const shopsCount = ref(0)
const error = ref('')
const tab = ref('products')

const STATUS = {
  pending_payment: '⏳ Ждёт оплаты',
  paid: '✅ Оплачен — пора отправлять',
  fulfilled: '📦 Отправлен',
  delivered: '🎉 Доставлен',
  cancelled: '✖️ Отменён',
}
const TYPE_LABEL = { physical: 'товар', digital: 'digital', service: 'услуга' }

async function reload() {
  const id = botId.value
  ;[summary.value, stats.value, products.value, orders.value, mailings.value] =
    await Promise.all([
      fetchShopSummary(id),
      fetchShopStats(id),
      fetchProducts(id),
      fetchShopOrders(id),
      fetchMailings(id),
    ])
}

onMounted(async () => {
  try {
    const me = await fetchMe()
    shopsCount.value = me.bots.length
    await reload()
  } catch (e) {
    error.value = e.response?.data?.detail || 'Не удалось загрузить магазин'
  }
})

watch(botId, reload)

async function removeProduct(p) {
  await deleteProduct(botId.value, p.id)
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
    await fulfillOrder(botId.value, f.orderId, {
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

const mailingForm = ref({ text: '', button_text: '', button_url: '', sending: false })

async function submitMailing() {
  const f = mailingForm.value
  if (f.sending || !f.text) return
  f.sending = true
  try {
    await createMailing(botId.value, {
      text: f.text,
      button_text: f.button_text || null,
      button_url: f.button_url || null,
    })
    mailingForm.value = { text: '', button_text: '', button_url: '', sending: false }
    await reload()
  } finally {
    f.sending = false
  }
}
</script>

<template>
  <div class="shop">
    <p v-if="error" class="error">{{ error }}</p>
    <template v-else-if="summary">
      <header>
        <div class="title">
          <h2>Кабинет</h2>
          <div class="bot-line">
            <span class="dot" :class="{ off: !summary.is_active }" />
            <span>@{{ summary.bot_username }}</span>
          </div>
        </div>
        <button v-if="shopsCount > 1" class="switch" @click="router.push('/shops')">
          Магазины
        </button>
      </header>

      <div class="stats">
        <div class="card stat">
          <b class="num">{{ summary.customers_count }}</b><span>покупателей</span>
        </div>
        <div class="card stat">
          <b class="num">{{ summary.orders_count }}</b><span>заказов</span>
        </div>
        <div class="card stat green">
          <b class="num">{{ Number(summary.revenue).toFixed(0) }}</b><span>USDT</span>
        </div>
      </div>

      <nav>
        <button :class="{ active: tab === 'products' }" @click="tab = 'products'">Товары</button>
        <button :class="{ active: tab === 'orders' }" @click="tab = 'orders'">Заказы</button>
        <button :class="{ active: tab === 'mailings' }" @click="tab = 'mailings'">Рассылки</button>
        <button :class="{ active: tab === 'stats' }" @click="tab = 'stats'">Статистика</button>
      </nav>

      <template v-if="tab === 'products'">
        <button class="btn add" @click="router.push(`/shop/${botId}/product`)">
          + Добавить товар или услугу
        </button>
        <div v-for="p in products" :key="p.id" class="card row" :class="{ inactive: !p.is_active }">
          <div class="info">
            <b>{{ p.title }}</b>
            <span class="muted">
              {{ Number(p.price) }} USDT · {{ TYPE_LABEL[p.type] }}
              <template v-if="!p.is_active"> · скрыт</template>
            </span>
          </div>
          <div class="row-actions">
            <button @click="router.push(`/shop/${botId}/product/${p.id}`)">✏️</button>
            <button @click="removeProduct(p)">🗑</button>
          </div>
        </div>
        <p v-if="!products.length" class="empty">Товаров пока нет.</p>
      </template>

      <template v-else-if="tab === 'orders'">
        <div v-for="o in orders" :key="o.id" class="card order">
          <div class="order-head">
            <b>#{{ o.id }} · {{ Number(o.total).toFixed(2) }} {{ o.currency }}</b>
            <span class="badge">{{ STATUS[o.status] || o.status }}</span>
          </div>
          <span class="muted">
            {{ o.customer_username ? '@' + o.customer_username : o.customer_first_name || 'аноним' }}
          </span>
          <div v-if="o.comment" class="comment">💬 {{ o.comment }}</div>

          <button
            v-if="o.status === 'paid' && fulfillForm.orderId !== o.id"
            class="btn btn-green fulfill-btn"
            @click="openFulfill(o)"
          >
            Отправить покупателю
          </button>
          <div v-if="fulfillForm.orderId === o.id" class="fulfill-form">
            <input v-model="fulfillForm.tracking" placeholder="Трек-номер" />
            <input v-model="fulfillForm.url" placeholder="Ссылка (файл / инвайт)" />
            <input v-model="fulfillForm.note" placeholder="Примечание" />
            <div class="pair">
              <button class="btn btn-soft" @click="fulfillForm.orderId = null">Отмена</button>
              <button
                class="btn btn-green"
                :disabled="fulfillForm.sending || !(fulfillForm.tracking || fulfillForm.url || fulfillForm.note)"
                @click="submitFulfill"
              >
                {{ fulfillForm.sending ? '…' : 'Отправить' }}
              </button>
            </div>
          </div>
        </div>
        <p v-if="!orders.length" class="empty">Заказов пока нет.</p>
      </template>

      <template v-else-if="tab === 'mailings'">
        <div class="card mailing-form">
          <textarea v-model="mailingForm.text" rows="4" placeholder="Текст рассылки по базе этого магазина" />
          <input v-model="mailingForm.button_text" placeholder="Текст кнопки (опционально)" />
          <input v-model="mailingForm.button_url" placeholder="Ссылка кнопки" />
          <button
            class="btn btn-primary"
            :disabled="mailingForm.sending || !mailingForm.text || (!!mailingForm.button_text !== !!mailingForm.button_url)"
            @click="submitMailing"
          >
            {{ mailingForm.sending ? '…' : 'Отправить всем' }}
          </button>
        </div>
        <div v-for="m in mailings" :key="m.id" class="card row">
          <div class="info">
            <b>{{ m.text.slice(0, 60) }}{{ m.text.length > 60 ? '…' : '' }}</b>
            <span class="muted">
              {{ { pending: '⏳ В очереди', sending: '📤 Отправляется', done: '✅ Отправлена' }[m.status] || m.status }}
              <template v-if="m.status === 'done'"> · доставлено {{ m.sent_count }}</template>
            </span>
          </div>
        </div>
        <p v-if="!mailings.length" class="empty">Рассылок пока не было.</p>
      </template>

      <template v-else>
        <div v-if="stats" class="stats-grid">
          <div class="card metric">
            <b class="num">{{ stats.telegram_users }}</b><span>пользователей Telegram</span>
          </div>
          <div class="card metric">
            <b class="num">{{ stats.product_views }}</b><span>просмотров товаров</span>
          </div>
          <div class="card metric">
            <b class="num">{{ stats.checkout_starts }}</b><span>переходов к оплате</span>
          </div>
          <div class="card metric">
            <b class="num">{{ stats.purchases }}</b><span>покупок</span>
          </div>
          <div class="card metric green">
            <b class="num">{{ Number(stats.total_sales).toFixed(0) }}</b><span>USDT продаж</span>
          </div>
          <div class="card metric">
            <b class="num">{{ stats.repeat_customers }}</b><span>повторных покупателей</span>
          </div>
        </div>

        <div class="card plan">
          <div class="plan-head">
            <b>Выплаты</b>
            <span class="muted">комиссия {{ Number(summary.commission_pct) }}%</span>
          </div>
          <div class="plan-row">
            <span>Накоплено к выплате</span>
            <span class="num">{{ Number(summary.payout_pending).toFixed(2) }} USDT</span>
          </div>
          <p class="hint">
            Деньги уходят в @CryptoBot автоматически, когда накопится
            <span class="num">{{ Number(summary.payout_min).toFixed(2) }}</span> USDT.
          </p>
        </div>

        <div v-if="summary.limits" class="card plan">
          <div class="plan-head">
            <b>Тариф: {{ summary.limits.plan === 'pro' ? 'Pro' : 'Бесплатный' }}</b>
            <span v-if="!summary.limits.enforced" class="muted">лимиты пока не действуют</span>
          </div>
          <div class="plan-row">
            <span>Товары</span>
            <span>{{ summary.limits.products_used }}{{ summary.limits.products_cap ? ' из ' + summary.limits.products_cap : '' }}</span>
          </div>
          <div class="plan-row">
            <span>Услуги</span>
            <span>{{ summary.limits.services_used }}{{ summary.limits.services_cap ? ' из ' + summary.limits.services_cap : '' }}</span>
          </div>
          <div class="plan-row">
            <span>Рассылка</span>
            <span>{{ summary.limits.mailing_recipients_cap ? 'до ' + summary.limits.mailing_recipients_cap + ' получателей' : 'без лимита' }}</span>
          </div>
        </div>
      </template>
    </template>
  </div>
</template>

<style scoped>
.shop { padding: 18px 16px 36px; }
header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 14px; }
h2 { font-size: 18px; margin: 0 0 4px; }
.bot-line { display: flex; align-items: center; gap: 6px; font-size: 13px; color: var(--sub); }
.dot { width: 8px; height: 8px; border-radius: 50%; background: var(--green); }
.dot.off { background: var(--sub); }
.switch {
  border: 0; background: var(--surface2); color: var(--text); border-radius: 12px;
  padding: 9px 14px; font-size: 13px; font-weight: 700; cursor: pointer;
}
.stats { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.stat { padding: 12px 10px; display: flex; flex-direction: column; gap: 3px; }
.stat b { font-size: 19px; }
.stat span { font-size: 12px; font-weight: 700; color: var(--sub); }
.stat.green { background: var(--green-soft); }
.stat.green b, .stat.green span { color: var(--green-text); }
nav { display: flex; gap: 4px; background: var(--surface2); border-radius: 15px; padding: 4px; margin: 14px 0 12px; }
nav button {
  flex: 1; border: 0; border-radius: 11px; height: 37px; background: none; color: var(--text);
  font-size: 13px; font-weight: 700; cursor: pointer;
}
nav button.active { background: var(--accent); color: #fff; font-weight: 800; }
.add { background: var(--accent-soft); color: var(--accent); margin-bottom: 10px; }
.row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.row.inactive { opacity: 0.5; }
.info { display: flex; flex-direction: column; gap: 3px; }
.info span { font-size: 12px; }
.row-actions button { border: 0; background: none; font-size: 18px; cursor: pointer; }
.order { display: flex; flex-direction: column; gap: 8px; margin-bottom: 12px; }
.order-head { display: flex; justify-content: space-between; align-items: center; }
.badge {
  background: var(--surface2); border-radius: 12px; padding: 5px 11px;
  font-size: 11px; font-weight: 800;
}
.comment { background: var(--surface2); border-radius: 11px; padding: 9px 11px; font-size: 13px; }
.fulfill-btn { height: 42px; }
.fulfill-form { display: flex; flex-direction: column; gap: 8px; }
.pair { display: flex; gap: 8px; }
.pair .btn { height: 42px; }
.mailing-form { display: flex; flex-direction: column; gap: 10px; margin-bottom: 12px; }
.mailing-form textarea { resize: none; }
.stats-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.metric { display: flex; flex-direction: column; gap: 4px; padding: 14px 12px; }
.metric b { font-size: 21px; line-height: 1.1; }
.metric span { font-size: 12px; font-weight: 700; color: var(--sub); }
.metric.green { background: var(--green-soft); }
.metric.green b, .metric.green span { color: var(--green-text); }
.plan { margin-top: 12px; display: flex; flex-direction: column; gap: 9px; }
.plan-head { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
.plan-head .muted { font-size: 12px; }
.plan-row { display: flex; justify-content: space-between; font-size: 14px; }
.plan-row span:first-child { color: var(--sub); font-weight: 700; }
.plan .hint { margin: 2px 0 0; font-size: 12px; line-height: 1.45; color: var(--sub); }
.empty { text-align: center; color: var(--sub); margin-top: 24px; }
.error { text-align: center; color: var(--red); margin-top: 40px; }
</style>
