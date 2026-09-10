<script setup>
/**
 * Страница перевода по реквизитам продавца.
 *
 * Деньги идут мимо платформы: она показывает реквизиты, ведёт переписку и
 * ждёт, пока продавец подтвердит поступление. Поэтому здесь три вещи и
 * ничего лишнего — куда переводить, кнопка «я оплатил» и чат с продавцом.
 * «Я оплатил» заказ не оплачивает: это заявка, снимающая заказ с таймера.
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { claimOrderPaid, fetchMyOrders } from '../api'
import { t } from '../i18n'
import { apiError } from '../services/apiError'
import OrderChat from '../components/OrderChat.vue'

const route = useRoute()
const router = useRouter()
const orderId = Number(route.params.orderId)

const order = ref(null)
const error = ref('')
const claiming = ref(false)
const copied = ref('')

// Отсчёт до автоотмены. Тикает, только пока перевод не отмечен: после
// «я оплатил» заказ ждёт продавца сколько угодно.
const now = ref(Date.now())
let timer = null

const details = computed(() => order.value?.payment_details || null)
const claimed = computed(() => Boolean(order.value?.paid_claimed_at))

const timeLeft = computed(() => {
  if (!order.value?.expires_at || claimed.value) return null
  const total = Math.floor((new Date(order.value.expires_at).getTime() - now.value) / 1000)
  if (total <= 0) return null
  const m = Math.floor(total / 60)
  return `${m}:${String(total % 60).padStart(2, '0')}`
})
const expired = computed(
  () =>
    !claimed.value &&
    order.value?.expires_at &&
    new Date(order.value.expires_at).getTime() <= now.value,
)

async function load() {
  try {
    const orders = await fetchMyOrders(true)
    order.value = orders.find((o) => o.id === orderId) || null
    if (!order.value) error.value = t('pay.notFound')
  } catch (e) {
    error.value = apiError(e, 'pay.loadError')
  }
}

onMounted(() => {
  load()
  timer = setInterval(() => (now.value = Date.now()), 1000)
})
onUnmounted(() => clearInterval(timer))

// Копирование: буфер обмена в Telegram WebView бывает недоступен, поэтому
// на отказ отвечаем выделением текста, а не молчанием.
async function copy(value, field) {
  try {
    await navigator.clipboard.writeText(String(value))
    copied.value = field
    setTimeout(() => (copied.value = ''), 1500)
  } catch {
    error.value = t('pay.copyFailed')
  }
}

async function claim() {
  if (claiming.value) return
  claiming.value = true
  error.value = ''
  try {
    order.value = await claimOrderPaid(orderId)
  } catch (e) {
    error.value = apiError(e, 'pay.claimError')
  } finally {
    claiming.value = false
  }
}

function kindLabel(kind) {
  return t(`pay.kind.${kind || 'other'}`)
}
</script>

<template>
  <div class="pay">
    <a class="back" @click="router.push('/my-orders')">← {{ t('orders.title') }}</a>

    <template v-if="order">
      <h2>{{ t('pay.orderTitle', { n: order.id }) }}</h2>

      <!-- сумма: главное, что должно совпасть до копейки -->
      <div class="amount">
        <span class="cap">{{ t('pay.amount') }}</span>
        <div class="value">
          <b>{{ Number(order.total).toFixed(2) }} {{ order.currency }}</b>
          <button class="copy" type="button" @click="copy(Number(order.total).toFixed(2), 'sum')">
            {{ copied === 'sum' ? t('pay.copied') : t('pay.copy') }}
          </button>
        </div>
      </div>

      <p v-if="timeLeft" class="timer">{{ t('pay.timeLeft', { time: timeLeft }) }}</p>
      <p v-else-if="expired" class="timer out">{{ t('pay.expired') }}</p>

      <!-- реквизиты — снимок на момент заказа: продавец мог их уже поменять -->
      <section v-if="details" class="card">
        <div class="head">
          <b>{{ details.label }}</b>
          <span class="kind">{{ kindLabel(details.kind) }}</span>
        </div>
        <div class="field">
          <span class="cap">{{ t(`pay.field.${details.kind || 'other'}`) }}</span>
          <div class="value">
            <b class="mono">{{ details.account }}</b>
            <button class="copy" type="button" @click="copy(details.account, 'acc')">
              {{ copied === 'acc' ? t('pay.copied') : t('pay.copy') }}
            </button>
          </div>
        </div>
        <div v-if="details.holder" class="field">
          <span class="cap">{{ t('pay.holder') }}</span>
          <div class="value"><b>{{ details.holder }}</b></div>
        </div>
        <p v-if="details.note" class="note">
          <span class="cap">{{ t('pay.note') }}</span>{{ details.note }}
        </p>
      </section>

      <!-- состояние: до отметки объясняем порядок, после — что происходит -->
      <p v-if="!claimed" class="lead">{{ t('pay.beforeYouPay') }}</p>
      <div v-else class="claimed">
        <b>{{ t('pay.claimed') }}</b>
        <span>{{ t('pay.claimedHint') }}</span>
      </div>

      <p class="warn">{{ t('pay.warning') }}</p>
      <p v-if="error" class="error">{{ error }}</p>

      <button
        v-if="!claimed && order.status === 'pending_payment'"
        class="btn btn-primary claim"
        :disabled="claiming"
        @click="claim"
      >
        {{ claiming ? t('pay.claiming') : t('pay.claim') }}
      </button>

      <!-- чат открыт с оформления: договориться о переводе больше негде -->
      <h3 class="chat-title">{{ t('pay.chat') }}</h3>
      <div class="chat-box"><OrderChat mode="buyer" :order-id="order.id" /></div>
    </template>

    <p v-else-if="error" class="error">{{ error }}</p>
  </div>
</template>

<style scoped lang="scss">
.pay { padding: 16px 16px 32px; display: flex; flex-direction: column; gap: 12px; }
.back { color: var(--sub); font-size: 14px; font-weight: 700; cursor: pointer; }
h2 { margin: 0; font-size: 18px; }
.cap { display: block; font-size: 12px; color: var(--sub); margin-bottom: 3px; }
.amount, .card {
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 12px 13px;
  background: var(--surface);
}
.amount .value b { font-size: 20px; }
.value { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.mono { font-family: ui-monospace, 'SF Mono', Menlo, monospace; word-break: break-all; }
.copy {
  flex-shrink: 0; border: 1px solid var(--border); background: var(--surface2);
  color: var(--text); border-radius: 9px; padding: 6px 10px; font-size: 12px;
  font-weight: 700; cursor: pointer;
}
.card { display: flex; flex-direction: column; gap: 11px; }
.card .head { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
.card .head b { font-size: 15px; }
.kind { font-size: 12px; color: var(--sub); }
.note { margin: 0; font-size: 13px; line-height: 1.45; }
.timer { margin: 0; font-size: 13px; font-weight: 700; color: var(--orange-text); }
.timer.out { color: var(--red); }
.lead { margin: 0; font-size: 13.5px; color: var(--sub); line-height: 1.5; }
.claimed {
  display: flex; flex-direction: column; gap: 4px;
  background: var(--green-soft, var(--surface2)); border-radius: 13px; padding: 12px 13px;
  b { font-size: 14px; }
  span { font-size: 13px; color: var(--sub); line-height: 1.45; }
}
.warn { margin: 0; font-size: 12px; color: var(--sub); line-height: 1.45; }
.error { color: var(--red); margin: 0; font-size: 13px; }
.claim { width: 100%; }
.chat-title { margin: 10px 0 0; font-size: 15px; }
.chat-box { height: 340px; display: flex; }
</style>
