<script setup>
// Список покупок покупателя: живые статусы, форма оценки, удаление отзыва.
// Живёт и на отдельном экране /my-orders, и внутри профиля.
import { onBeforeUnmount, onMounted, ref } from 'vue'
import {
  cancelOrder,
  confirmReceived,
  deleteOrderReview,
  fetchMyOrders,
  payOrder,
  submitOrderReviews,
} from '../api'
import { t } from '../i18n'
import { openTelegramLink } from '../services/telegram'
import { apiError } from '../services/apiError'

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
    sendError.value = apiError(e, 'orders.sendError')
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
    sendError.value = apiError(e, 'orders.deleteError')
  }
}

// --- неоплаченный заказ: свежая ссылка на оплату или отмена покупателем ---
const busyId = ref(null)
const actionError = ref({ id: null, text: '' })

// Часовой таймер неоплаченного заказа. Один тик на весь список, а не на
// карточку: отсчёт виден ровно у заказов со сроком из expires_at, ноль —
// строка пропадает (после прохода джоба на бэкенде уйдёт и сам заказ).
const now = ref(Date.now())
let countdownTimer = null

function timeLeft(o) {
  if (!o.expires_at) return null
  const total = Math.floor((new Date(o.expires_at).getTime() - now.value) / 1000)
  if (total <= 0) return null
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`
}

// Отмена убирает карточку из списка — короткий тост, чтобы нажатие не
// выглядело сбоем
const toast = ref('')
let toastTimer = null

function showToast(text) {
  toast.value = text
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => (toast.value = ''), 3500)
}

async function retryPay(o) {
  busyId.value = o.id
  actionError.value = { id: null, text: '' }
  try {
    const { payment_url } = await payOrder(o.id)
    if (payment_url) {
      // тот же канал, что и сразу после чекаута — окно @CryptoBot
      openTelegramLink(payment_url)
    } else {
      actionError.value = { id: o.id, text: t('orders.payUnavailable') }
    }
  } catch (e) {
    actionError.value = { id: o.id, text: apiError(e, 'orders.payError') }
  } finally {
    busyId.value = null
  }
}

// Отправка и получение — разные события: пока покупатель не подтвердил, чат
// с продавцом остаётся открытым, а оценивать ещё нечего.
async function confirmDelivery(o) {
  busyId.value = o.id
  actionError.value = { id: null, text: '' }
  try {
    await confirmReceived(o.id)
    await refresh()
  } catch (e) {
    actionError.value = { id: o.id, text: apiError(e, 'orders.receivedError') }
  } finally {
    busyId.value = null
  }
}

async function doCancel(o) {
  if (!window.confirm(t('orders.cancelConfirm', { n: o.id }))) return
  busyId.value = o.id
  actionError.value = { id: null, text: '' }
  try {
    await cancelOrder(o.id)
    // статус сменился на сервере — подтягиваем, не дожидаясь опроса
    await refresh()
    showToast(t('orders.cancelledNote', { n: o.id }))
  } catch (e) {
    actionError.value = { id: o.id, text: apiError(e, 'orders.cancelError') }
  } finally {
    busyId.value = null
  }
}

// Статусы меняются на бэкенде (вебхук оплаты, отправка продавцом) — обновляем
// сами, без перезахода. Опрос только пока вкладка видима, как в OrderChat:
// в свёрнутом Telegram таймер не нужен.
let timer = null

async function refresh(silent = false) {
  try {
    // тихо: прошлые данные остаются на экране, ошибки сети не роняем
    orders.value = await fetchMyOrders(silent)
  } catch {
    /* покажем данные прошлой загрузки */
  }
}

function refreshIfVisible() {
  if (document.visibilityState === 'visible') refresh(true)  // фоновый — без оверлея
}

onMounted(async () => {
  await refresh()
  timer = setInterval(refreshIfVisible, 10_000)
  countdownTimer = setInterval(() => (now.value = Date.now()), 1000)
  document.addEventListener('visibilitychange', refreshIfVisible)
})

onBeforeUnmount(() => {
  clearInterval(timer)
  clearInterval(countdownTimer)
  clearTimeout(toastTimer)
  document.removeEventListener('visibilitychange', refreshIfVisible)
})
</script>

<template>
  <div class="orders-list">
    <template v-if="orders && !orders.length">
      <p class="empty">{{ t('orders.empty') }}</p>
    </template>
    <div v-for="o in orders || []" :key="o.id" class="order">
      <div class="head">
        <b>{{ t('orders.number', { n: o.id }) }}</b>
        <span class="status" :class="STATUS_CLASS[o.status] || 'wait'">
          {{ STATUS_KEY[o.status] ? t(STATUS_KEY[o.status]) : o.status }}
        </span>
      </div>
      <!-- ключ по индексу: у двух вариаций одного товара product_id общий,
           а список перезапрашивается каждые 10 секунд — на дублирующемся
           ключе Vue переиспользует узлы наугад -->
      <div v-for="(i, n) in o.items" :key="n" class="item">
        {{ i.title }}<span v-if="i.variant_label" class="variant"> · {{ i.variant_label }}</span>
        × {{ i.qty }} — {{ (Number(i.price) * i.qty).toFixed(2) }} USDT
        <span v-if="i.reviewed" class="reviewed-mark">{{
          i.my_review?.status === 'pending' ? t('reviews.statusPending') : t('orders.reviewedMark')
        }}</span>
      </div>
      <!-- итог и, у неоплаченного, таймер до отмены — в одну строку -->
      <div class="total">
        <span>{{ t('orders.total', { sum: `${Number(o.total).toFixed(2)} ${o.currency}` }) }}</span>
        <span v-if="timeLeft(o)" class="time-left">{{ timeLeft(o) }}</span>
      </div>
      <!-- действия — внизу карточки: сначала состав и сумма, потом кнопки.
           неоплаченный: покупатель может доплатить заново или передумать -->
      <template v-if="o.status === 'pending_payment'">
        <div class="pay-actions">
          <button class="pay-btn" :disabled="busyId === o.id" @click="retryPay(o)">
            {{ t('orders.payNow') }}
          </button>
          <button class="cancel-btn" :disabled="busyId === o.id" @click="doCancel(o)">
            {{ t('orders.cancelOrder') }}
          </button>
        </div>
        <p v-if="actionError.id === o.id" class="action-error">{{ actionError.text }}</p>
      </template>
      <!-- отправлен, но ещё не получен: отметку ставит покупатель -->
      <template v-if="o.status === 'fulfilled'">
        <div class="pay-actions">
          <button class="pay-btn" :disabled="busyId === o.id" @click="confirmDelivery(o)">
            {{ t('orders.received') }}
          </button>
        </div>
        <p v-if="actionError.id === o.id" class="action-error">{{ actionError.text }}</p>
      </template>
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
          <textarea
            v-model="drafts[i.product_id].body"
            class="rate-note"
            :placeholder="t('orders.notePlaceholder')"
            maxlength="1000"
            rows="3"
          />
        </div>
        <p v-if="sendError" class="rate-error">{{ sendError }}</p>
        <div class="form-actions">
          <button class="btn btn-primary" :disabled="sending" @click="submit(o)">
            {{ sending ? t('orders.sending') : t('orders.submit') }}
          </button>
          <button class="later-btn" type="button" @click="formFor = null">{{ t('orders.later') }}</button>
        </div>
      </div>
    </div>
    <div v-if="toast" class="toast">{{ toast }}</div>
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
  .total {
    margin-top: 6px;
    font-weight: 700;
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 8px;
  }
}
.empty { text-align: center; opacity: 0.6; margin-top: 40px; }
.pay-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}
.pay-actions button {
  flex: 1;
  height: 36px;
  border: 0;
  border-radius: 11px;
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
}
.pay-btn { background: var(--green); color: var(--on-green); }
.cancel-btn { background: var(--surface2); color: var(--red); }
.action-error { color: var(--red); font-size: 12px; margin: 6px 0 0; }
.time-left {
  font-size: 12px;
  font-weight: 700;
  color: var(--sub);
  font-variant-numeric: tabular-nums;
}
.toast {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--surface2);
  color: var(--text);
  font-size: 13px;
  font-weight: 700;
  padding: 10px 16px;
  border-radius: 12px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
  z-index: 10;
  white-space: nowrap;
}
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
.variant { color: var(--sub); }
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
  width: 100%;
  box-sizing: border-box;
  min-height: 76px; /* выше одной строки: место для пары слов */
  resize: none;
}
.rate-error { color: var(--red); font-size: 12.5px; margin: 0; }
.form-actions {
  display: flex;
  gap: 8px;
  button { flex: 1; height: 42px; border-radius: 11px; }
}
.later-btn {
  border: 0;
  background: var(--surface2);
  color: var(--sub);
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
}
.status {
  &.ok { color: var(--green); }
  &.bad { color: var(--red); }
  &.wait { opacity: 0.7; }
}
</style>
