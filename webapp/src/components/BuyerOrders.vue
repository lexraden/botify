<script setup>
// Список покупок покупателя: живые статусы, форма оценки, удаление отзыва.
// Живёт и на отдельном экране /my-orders, и внутри профиля.
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { deleteOrderReview, fetchMyOrders, submitOrderReviews } from '../api'
import { t } from '../i18n'

const router = useRouter()
const orders = ref(null)

// класс для цвета статуса: ok — зелёный, bad — красный, wait — нейтральный
const STATUS_CLASS = {
  pending_payment: 'wait',
  paid: 'ok',
  fulfilled: 'ok',
  delivered: 'ok',
  cancelled: 'bad',
}
const STATUS_KEY = {
  pending_payment: 'orders.statusPendingPayment',
  paid: 'orders.statusPaid',
  fulfilled: 'orders.statusFulfilled',
  delivered: 'orders.statusDelivered',
  cancelled: 'orders.statusCancelled',
}

// --- отзыв о доставленном заказе: создание, правка, удаление ---
const formFor = ref(null) // id заказа с раскрытой формой
const drafts = ref({}) // product_id -> { rating, body }
const sending = ref(false)
const sendError = ref('')

const canRate = (o) => o.status === 'delivered' && o.items.length > 0
const allReviewed = (o) => o.items.every((i) => i.reviewed)

function openForm(o) {
  formFor.value = o.id
  sendError.value = ''
  // уже оценённые позиции открываются заполненными — правим, а не пишем заново
  drafts.value = Object.fromEntries(
    o.items.map((i) => [
      i.product_id,
      { rating: i.my_review?.rating ?? 0, body: i.my_review?.body ?? '' },
    ]),
  )
}

async function submit(o) {
  if (o.items.some((i) => !drafts.value[i.product_id]?.rating)) {
    sendError.value = t('orders.needEveryRating')
    return
  }
  sending.value = true
  sendError.value = ''
  try {
    await submitOrderReviews(
      o.id,
      o.items.map((i) => ({
        product_id: i.product_id,
        rating: drafts.value[i.product_id].rating,
        body: drafts.value[i.product_id].body.trim() || null,
      })),
    )
    formFor.value = null
    // флаги и тексты отзывов приходят с сервера
    await refresh()
  } catch (e) {
    sendError.value = e.response?.data?.detail || t('orders.sendError')
  } finally {
    sending.value = false
  }
}

async function removeReview(o, productId) {
  sendError.value = ''
  try {
    await deleteOrderReview(o.id, productId)
    formFor.value = null
    await refresh()
  } catch (e) {
    sendError.value = e.response?.data?.detail || t('orders.deleteError')
  }
}

// Статусы меняются на бэкенде (вебхук оплаты, отправка продавцом) — обновляем
// сами, без перезахода. Опрос только пока вкладка видима, как в OrderChat:
// в свёрнутом Telegram таймер не нужен.
let timer = null

async function refresh() {
  try {
    // тихо: прошлые данные остаются на экране, ошибки сети не роняем
    orders.value = await fetchMyOrders()
  } catch {
    /* покажем данные прошлой загрузки */
  }
}

function refreshIfVisible() {
  if (document.visibilityState === 'visible') refresh()
}

onMounted(async () => {
  await refresh()
  timer = setInterval(refreshIfVisible, 10_000)
  document.addEventListener('visibilitychange', refreshIfVisible)
})

onBeforeUnmount(() => {
  clearInterval(timer)
  document.removeEventListener('visibilitychange', refreshIfVisible)
})
</script>

<template>
  <div class="orders-list">
    <template v-if="orders && !orders.length">
      <p class="empty">{{ t('orders.empty') }}</p>
      <button class="btn btn-primary empty-cta" @click="router.push('/')">{{ t('common.toCatalog') }}</button>
    </template>
    <div v-for="o in orders || []" :key="o.id" class="order">
      <div class="head">
        <b>{{ t('orders.number', { n: o.id }) }}</b>
        <span class="status" :class="STATUS_CLASS[o.status] || 'wait'">
          {{ STATUS_KEY[o.status] ? t(STATUS_KEY[o.status]) : o.status }}
        </span>
      </div>
      <div v-for="i in o.items" :key="i.product_id" class="item">
        {{ i.title }} × {{ i.qty }} — {{ (Number(i.price) * i.qty).toFixed(2) }} USDT
        <span v-if="i.reviewed" class="reviewed-mark">{{ t('orders.reviewedMark') }}</span>
      </div>
      <div class="total">{{ t('orders.total', { sum: `${Number(o.total).toFixed(2)} ${o.currency}` }) }}</div>

      <button v-if="canRate(o) && formFor !== o.id" class="rate-btn" @click="openForm(o)">
        {{ allReviewed(o) ? t('orders.editReview') : t('orders.rate') }}
      </button>

      <div v-if="formFor === o.id" class="review-form">
        <!-- сервер принимает оценку только по своему доставленному заказу -->
        <div v-for="i in o.items" :key="i.product_id" class="rate-row">
          <div class="rate-title-line">
            <span class="rate-title">{{ i.title }}</span>
            <a v-if="i.reviewed" class="del" @click="removeReview(o, i.product_id)">{{ t('orders.delete') }}</a>
          </div>
          <div class="stars">
            <button
              v-for="n in 5"
              :key="n"
              :class="{ on: n <= drafts[i.product_id].rating }"
              @click="drafts[i.product_id].rating = n"
            >
              ★
            </button>
          </div>
          <input
            v-model="drafts[i.product_id].body"
            class="rate-note"
            :placeholder="t('orders.notePlaceholder')"
            maxlength="1000"
          />
        </div>
        <p v-if="sendError" class="rate-error">{{ sendError }}</p>
        <div class="form-actions">
          <button class="btn btn-primary" :disabled="sending" @click="submit(o)">
            {{ sending ? t('orders.sending') : t('orders.submit') }}
          </button>
          <a @click="formFor = null">{{ t('orders.later') }}</a>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.order {
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 12px;
  margin-bottom: 10px;
  .head { display: flex; justify-content: space-between; margin-bottom: 6px; }
  .item { font-size: 13px; padding: 2px 0; }
  .total { margin-top: 6px; font-weight: 700; }
}
.empty { text-align: center; opacity: 0.6; margin-top: 40px; }
.empty-cta { display: block; width: max-content; margin: 16px auto 0; }
.reviewed-mark {
  color: #f59e1b;
  font-size: 11px;
  font-weight: 700;
  margin-left: 4px;
}
.rate-btn {
  width: 100%;
  margin-top: 8px;
  height: 36px;
  border: 0;
  border-radius: 11px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
}
.review-form { margin-top: 10px; display: flex; flex-direction: column; gap: 10px; }
.rate-row {
  border-top: 1px solid var(--surface2);
  padding-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.rate-title { font-size: 13px; font-weight: 700; }
.rate-title-line {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
}
.del {
  color: var(--red);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}
.stars { display: flex; gap: 4px; }
.stars button {
  border: 0;
  background: none;
  font-size: 24px;
  line-height: 1;
  color: var(--surface2);
  cursor: pointer;
  padding: 0 2px;
}
.stars button.on { color: #f59e1b; }
.rate-note {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 8px 10px;
  font-size: 13px;
  font-family: inherit;
  background: var(--surface);
  color: var(--text);
}
.rate-error { color: var(--red); font-size: 12.5px; margin: 0; }
.form-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  a { color: var(--sub); font-size: 13px; font-weight: 700; cursor: pointer; }
}
.status {
  &.ok { color: var(--green); }
  &.bad { color: var(--red); }
  &.wait { opacity: 0.7; }
}
</style>
