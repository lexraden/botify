<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
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
  fetchSellerReviews,
  fulfillOrder,
  replyToReview,
  withdrawPayout,
} from '../api'
import { t, intlLocale } from '../i18n'
import { openTelegramLink } from '../services/telegram'

const route = useRoute()
const router = useRouter()
const botId = computed(() => route.params.botId)

const summary = ref(null)
const stats = ref(null)
const products = ref([])
const orders = ref([])
const mailings = ref([])
const reviews = ref([])
const error = ref('')
// форма ответа на отзыв: один ответ на отзыв, повторная отправка правит его
const replyForm = ref({ reviewId: null, body: '', sending: false })
const replyError = ref('')

function openReply(r) {
  replyError.value = ''
  replyForm.value = { reviewId: r.id, body: r.reply_body || '', sending: false }
}

async function sendReply() {
  const f = replyForm.value
  if (!f.body.trim() || f.sending) return
  f.sending = true
  try {
    const updated = await replyToReview(botId.value, f.reviewId, f.body.trim())
    reviews.value = reviews.value.map((r) => (r.id === updated.id ? updated : r))
    replyForm.value = { reviewId: null, body: '', sending: false }
  } catch (e) {
    replyError.value = e.response?.data?.detail || t('reviews.sendError')
  } finally {
    f.sending = false
  }
}
// вкладка восстанавливается из ?tab= — возврат из чата заказа открывает заказы
const tab = ref(['products', 'orders', 'mailings', 'stats'].includes(route.query.tab)
  ? route.query.tab
  : 'products')

// --- кошелёк магазина ---
const withdrawing = ref(false)
const withdrawNote = ref('')
const withdrawFailed = ref(false)

const money = (v) => Number(v ?? 0)
const balance = computed(() => money(summary.value?.payout_pending))
const paidOut = computed(() => money(summary.value?.payout_paid))
const earned = computed(() => balance.value + paidOut.value)
const minPayout = computed(() => money(summary.value?.payout_min))
const canWithdraw = computed(() => balance.value > 0 && balance.value >= minPayout.value)
const leftToMin = computed(() => Math.max(0, minPayout.value - balance.value))

// словари надписей строятся как computed, чтобы переключение языка
// в профиле обновляло кабинет без перезахода
const WITHDRAW_ERROR = computed(() => ({
  no_funds: t('withdraw.no_funds'),
  below_min: t('withdraw.below_min'),
  no_token: t('withdraw.no_token'),
  too_small: t('withdraw.too_small'),
  failed: t('withdraw.failed'),
  // деньги на месте, но часть долей ждёт завершения прошлой пачки — самая
  // нервная точка продукта, безымянного «не получилось» тут быть не должно
  nothing_to_send: t('withdraw.nothing_to_send'),
}))

// Единственный отказ, который продавец может исправить сам: @CryptoBot ещё
// не открыт. Заранее об этом не спрашиваем — API проверить не умеет, а сама
// попытка перевода отвечает точно. Показываем шаг только когда он понадобился.
const CRYPTOBOT_URL = 'https://t.me/CryptoBot'
const needsCryptobot = ref(false)

function openCryptobot() {
  openTelegramLink(CRYPTOBOT_URL)
}

async function onWithdraw() {
  if (!canWithdraw.value || withdrawing.value) return
  withdrawing.value = true
  withdrawNote.value = ''
  withdrawFailed.value = false
  try {
    const res = await withdrawPayout(botId.value)
    needsCryptobot.value = res.reason === 'cryptobot_not_started'
    withdrawFailed.value = !res.ok && !needsCryptobot.value
    withdrawNote.value = res.ok
      ? t('withdraw.sent', { sum: Number(res.sent).toFixed(2) })
      : needsCryptobot.value
        ? ''
        : WITHDRAW_ERROR.value[res.reason] || t('withdraw.generic')
    summary.value = await fetchShopSummary(botId.value)
  } catch {
    withdrawFailed.value = true
    withdrawNote.value = t('withdraw.retryFailed')
  } finally {
    withdrawing.value = false
  }
}

// Продавец ушёл нажимать Start и вернулся — это и есть его «я готов»,
// отдельной кнопки для подтверждения не нужно: повторяем вывод сами.
function retryOnReturn() {
  if (document.visibilityState === 'visible' && needsCryptobot.value) onWithdraw()
}

onMounted(() => document.addEventListener('visibilitychange', retryOnReturn))
onUnmounted(() => document.removeEventListener('visibilitychange', retryOnReturn))

const STATUS = computed(() => ({
  pending_payment: t('seller.statusPending'),
  paid: t('seller.statusPaid'),
  fulfilled: t('seller.statusFulfilled'),
  delivered: t('seller.statusDelivered'),
  cancelled: t('seller.statusCancelled'),
}))
// у оплаченных заказов есть чат с покупателем (закрывается сам через 72ч после доставки)
const CHAT_STATUSES = ['paid', 'fulfilled', 'delivered']
// Отправить можно оплаченный, а отправленный — переотправить: опечатку
// в треке продавец должен уметь поправить, пока посылка едет.
const FULFILLABLE = ['paid', 'fulfilled']
const TYPE_LABEL = computed(() => ({
  physical: t('type.physical'),
  digital: t('type.digital'),
  service: t('type.service'),
}))
const TYPE_EMOJI = { physical: '📦', digital: '📕', service: '🛎' }

// заказы приходят без данных покупателя (анонимность) — вместо них дата
const fmtDateTime = (iso) =>
  new Date(iso).toLocaleString(intlLocale(), {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })

// что продавец отправил при выполнении — одной строкой для карточки
const fulfillmentLine = (f) =>
  [
    f?.tracking ? t('fulfill.tracking', { v: f.tracking }) : '',
    f?.url ? t('fulfill.url', { v: f.url }) : '',
    f?.note || '',
  ]
    .filter(Boolean)
    .join(' · ')

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
  // отзывы — второстепенно: не грузятся, остальной кабинет всё равно работает
  reviews.value = await fetchSellerReviews(id).catch(() => [])
}

onMounted(async () => {
  try {
    await fetchMe()  // проверка сессии продавца
    await reload()
  } catch (e) {
    error.value = e.response?.data?.detail || t('seller.loadError')
  }
})

watch(botId, reload)

// Ошибки действий кабинета: удаление товара, выполнение заказа, рассылка.
// Без catch они гасли молча — продавец ждал срабатывания, а его не было.
const actionError = ref('')

watch(tab, () => {
  actionError.value = ''
})

async function removeProduct(p) {
  actionError.value = ''
  try {
    await deleteProduct(botId.value, p.id)
    await reload()
  } catch (e) {
    actionError.value = e.response?.data?.detail || t('seller.deleteError')
  }
}

const fulfillForm = ref({ orderId: null, tracking: '', url: '', note: '', sending: false })

function openFulfill(o) {
  fulfillForm.value = { orderId: o.id, tracking: '', url: '', note: '', sending: false }
}

async function submitFulfill() {
  const f = fulfillForm.value
  if (f.sending || !(f.tracking || f.url || f.note)) return
  f.sending = true
  actionError.value = ''
  try {
    await fulfillOrder(botId.value, f.orderId, {
      tracking: f.tracking || null,
      url: f.url || null,
      note: f.note || null,
    })
    fulfillForm.value.orderId = null
    await reload()
  } catch (e) {
    actionError.value = e.response?.data?.detail || t('seller.fulfillError')
  } finally {
    f.sending = false
  }
}

const mailingForm = ref({ text: '', button_text: '', button_url: '', sending: false })

async function submitMailing() {
  const f = mailingForm.value
  if (f.sending || !f.text) return
  f.sending = true
  actionError.value = ''
  try {
    await createMailing(botId.value, {
      text: f.text,
      button_text: f.button_text || null,
      button_url: f.button_url || null,
    })
    mailingForm.value = { text: '', button_text: '', button_url: '', sending: false }
    await reload()
  } catch (e) {
    actionError.value = e.response?.data?.detail || t('seller.mailingError')
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
          <h2>{{ t('seller.shop') }}</h2>
          <div class="bot-line">
            <span class="dot" :class="{ off: !summary.is_active }" />
            <span>@{{ summary.bot_username }}</span>
          </div>
        </div>
        <!-- профиль продавца: магазины, язык, тема. Системную «Назад» Telegram
             рисует сам (services/backButton.js), дубль в шапке не нужен -->
        <button class="icon-btn" :aria-label="t('seller.profileTitle')" @click="router.push(`/shop/${botId}/profile`)">
          <svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="8" r="4" />
            <path d="M4.5 20a7.5 7.5 0 0 1 15 0" />
          </svg>
        </button>
      </header>

      <div class="stats">
        <div class="card stat">
          <b class="num">{{ summary.customers_count }}</b><span>{{ t('stat.customers') }}</span>
        </div>
        <div class="card stat">
          <b class="num">{{ summary.orders_count }}</b><span>{{ t('stat.orders') }}</span>
        </div>
        <div class="card stat green">
          <b class="num">{{ balance.toFixed(2) }}</b><span>{{ t('wallet.balanceShort') }}</span>
        </div>
      </div>

      <nav>
        <button :class="{ active: tab === 'products' }" @click="tab = 'products'">{{ t('tab.products') }}</button>
        <button :class="{ active: tab === 'orders' }" @click="tab = 'orders'">{{ t('tab.orders') }}</button>
        <button :class="{ active: tab === 'mailings' }" @click="tab = 'mailings'">{{ t('tab.mailings') }}</button>
        <button :class="{ active: tab === 'stats' }" @click="tab = 'stats'">{{ t('tab.stats') }}</button>
      </nav>

      <p v-if="actionError" class="error-line">{{ actionError }}</p>

      <template v-if="tab === 'products'">
        <button class="btn add" @click="router.push(`/shop/${botId}/product`)">
          {{ t('seller.addProduct') }}
        </button>
        <div v-for="p in products" :key="p.id" class="card row" :class="{ inactive: !p.is_active }">
          <div class="row-left">
            <img v-if="p.image_url" class="prod-img" :src="p.image_url" :alt="p.title" />
            <span v-else class="prod-img prod-ph">{{ TYPE_EMOJI[p.type] }}</span>
            <div class="info">
              <b>{{ p.title }}</b>
              <span class="muted">
                {{ Number(p.price) }} USDT · {{ TYPE_LABEL[p.type] }}
                <template v-if="!p.is_active"> · {{ t('seller.hidden') }}</template>
              </span>
            </div>
          </div>
          <div class="row-actions">
            <button @click="router.push(`/shop/${botId}/product/${p.id}`)">✏️</button>
            <button @click="removeProduct(p)">🗑</button>
          </div>
        </div>
        <p v-if="!products.length" class="empty">{{ t('seller.noProducts') }}</p>
      </template>

      <template v-else-if="tab === 'orders'">
        <div v-for="o in orders" :key="o.id" class="card order">
          <div class="order-head">
            <b>#{{ o.id }} · {{ Number(o.total).toFixed(2) }} {{ o.currency }}</b>
            <span class="badge">{{ STATUS[o.status] || o.status }}</span>
          </div>
          <span class="muted">
            {{ fmtDateTime(o.created_at) }}
          </span>
          <!-- состав заказа: что именно куплено, сколько штук и на какую сумму -->
          <div class="items">
            <div v-for="i in o.items" :key="i.product_id" class="item">
              <span>{{ i.title }} × {{ i.qty }}</span>
              <span>{{ (Number(i.price) * i.qty).toFixed(2) }} USDT</span>
            </div>
          </div>
          <!-- адрес нужен, чтобы отправить: показываем отдельным блоком,
               а не в общем ряду примечаний -->
          <div v-if="o.delivery" class="delivery">
            <b>{{ t('seller.deliveryTitle') }}</b>
            <span>{{ o.delivery.name }} · {{ o.delivery.phone }}</span>
            <span>{{ o.delivery.address }}</span>
          </div>
          <div v-if="o.comment" class="comment">💬 {{ o.comment }}</div>
          <div v-if="o.fulfillment" class="comment">📤 {{ fulfillmentLine(o.fulfillment) }}</div>

          <button
            v-if="CHAT_STATUSES.includes(o.status)"
            class="btn btn-soft chat-btn"
            @click="router.push(`/shop/${botId}/orders/${o.id}/chat`)"
          >
            {{ t('seller.chatWithBuyer') }}
          </button>
          <button
            v-if="FULFILLABLE.includes(o.status) && fulfillForm.orderId !== o.id"
            class="btn btn-green fulfill-btn"
            @click="openFulfill(o)"
          >
            {{ t('seller.fulfill') }}
          </button>
          <div v-if="fulfillForm.orderId === o.id" class="fulfill-form">
            <input v-model="fulfillForm.tracking" :placeholder="t('seller.trackPh')" />
            <input v-model="fulfillForm.url" :placeholder="t('seller.urlPh')" />
            <input v-model="fulfillForm.note" :placeholder="t('seller.notePh')" />
            <div class="pair">
              <button class="btn btn-soft" @click="fulfillForm.orderId = null">{{ t('common.cancel') }}</button>
              <button
                class="btn btn-green"
                :disabled="fulfillForm.sending || !(fulfillForm.tracking || fulfillForm.url || fulfillForm.note)"
                @click="submitFulfill"
              >
                {{ fulfillForm.sending ? '…' : t('seller.send') }}
              </button>
            </div>
          </div>
        </div>
        <p v-if="!orders.length" class="empty">{{ t('seller.noOrders') }}</p>
      </template>

      <template v-else-if="tab === 'mailings'">
        <div class="card mailing-form">
          <textarea v-model="mailingForm.text" rows="4" :placeholder="t('seller.mailingTextPh')" />
          <input v-model="mailingForm.button_text" :placeholder="t('seller.mailingBtnTextPh')" />
          <input v-model="mailingForm.button_url" :placeholder="t('seller.mailingBtnUrlPh')" />
          <button
            class="btn btn-primary"
            :disabled="mailingForm.sending || !mailingForm.text || (!!mailingForm.button_text !== !!mailingForm.button_url)"
            @click="submitMailing"
          >
            {{ mailingForm.sending ? '…' : t('seller.sendAll') }}
          </button>
        </div>
        <div v-for="m in mailings" :key="m.id" class="card row">
          <div class="info">
            <b>{{ m.text.slice(0, 60) }}{{ m.text.length > 60 ? '…' : '' }}</b>
            <span class="muted">
              {{ { pending: t('mailing.pending'), sending: t('mailing.sending'), done: t('mailing.done') }[m.status] || m.status }}
              <template v-if="m.status === 'done'"> {{ t('seller.deliveredN', { n: m.sent_count }) }}</template>
            </span>
          </div>
        </div>
        <p v-if="!mailings.length" class="empty">{{ t('seller.noMailings') }}</p>
      </template>

      <template v-else>
        <div v-if="stats" class="stats-grid">
          <div class="card metric">
            <b class="num">{{ stats.telegram_users }}</b><span>{{ t('stat.telegramUsers') }}</span>
          </div>
          <div class="card metric">
            <b class="num">{{ stats.product_views }}</b><span>{{ t('stat.productViews') }}</span>
          </div>
          <div class="card metric">
            <b class="num">{{ stats.checkout_starts }}</b><span>{{ t('stat.checkoutStarts') }}</span>
          </div>
          <div class="card metric">
            <b class="num">{{ stats.purchases }}</b><span>{{ t('stat.purchases') }}</span>
          </div>
          <div class="card metric green">
            <b class="num">{{ Number(stats.total_sales).toFixed(2) }}</b><span>{{ t('stat.turnover') }}</span>
          </div>
          <div class="card metric">
            <b class="num">{{ stats.repeat_customers }}</b><span>{{ t('stat.repeatCustomers') }}</span>
          </div>
        </div>

        <div class="card wallet">
          <span class="wallet-label">{{ t('wallet.label') }}</span>
          <div class="wallet-sum">
            <b class="num">{{ balance.toFixed(2) }}</b><span>USDT</span>
          </div>
          <!-- Про @CryptoBot говорим только когда он реально понадобился:
               после отказа перевода. В обычном случае экран о нём молчит. -->
          <template v-if="needsCryptobot">
            <p class="wallet-state wait">{{ t('wallet.cryptobotHint') }}</p>
            <button class="btn btn-green wallet-btn" @click="openCryptobot">
              {{ t('wallet.openCryptobot') }}
            </button>
            <p class="hint">{{ t('wallet.returnHint') }}</p>
          </template>
          <template v-else>
            <p class="wallet-state" :class="canWithdraw ? 'ready' : 'wait'">
              <template v-if="canWithdraw">{{ t('wallet.ready') }}</template>
              <template v-else-if="balance > 0">
                {{ t('wallet.needMore', { n: leftToMin.toFixed(2) }) }}
              </template>
              <template v-else>{{ t('wallet.accumulates') }}</template>
            </p>
            <button
              class="btn btn-green wallet-btn"
              :disabled="!canWithdraw || withdrawing"
              @click="onWithdraw"
            >
              {{ withdrawing ? t('wallet.withdrawing') : t('wallet.withdraw') }}
            </button>
            <p v-if="withdrawNote" class="wallet-note" :class="{ err: withdrawFailed }">
              {{ withdrawNote }}
            </p>
          </template>

          <div class="wallet-rows">
            <div class="plan-row">
              <span>{{ t('wallet.earnedTotal') }}</span>
              <span class="num">{{ earned.toFixed(2) }} USDT</span>
            </div>
            <div class="plan-row">
              <span>{{ t('wallet.paidAlready') }}</span>
              <span class="num">{{ paidOut.toFixed(2) }} USDT</span>
            </div>
          </div>

          <p class="hint">
            {{ t('wallet.feeHint', { pct: Number(summary.commission_pct), min: minPayout }) }}
          </p>
        </div>

        <!-- что говорят покупатели: личность не раскрывается, только псевдоним -->
        <div v-if="reviews.length" class="card reviews-block">
          <b>{{ t('reviews.blockTitle') }}</b>
          <div v-for="r in reviews" :key="r.id" class="seller-review">
            <div class="sr-head">
              <span class="stars">
                {{ '★'.repeat(r.rating) }}<template v-if="r.author_name"> · {{ r.author_name }}</template>
              </span>
              <span class="muted sr-title">{{ r.product_title }}</span>
            </div>
            <p v-if="r.body">{{ r.body }}</p>

            <div v-if="r.reply_body" class="sr-reply">
              <b>{{ t('reviews.yourReply') }}</b>
              <p>{{ r.reply_body }}</p>
            </div>

            <template v-if="replyForm.reviewId === r.id">
              <textarea
                v-model="replyForm.body"
                class="reply-input"
                rows="2"
                maxlength="1000"
                :placeholder="t('reviews.replyPh')"
              ></textarea>
              <p v-if="replyError" class="reply-error">{{ replyError }}</p>
              <div class="pair">
                <button class="btn btn-green" :disabled="replyForm.sending" @click="sendReply">
                  {{ replyForm.sending ? t('wallet.withdrawing') : t('reviews.reply') }}
                </button>
                <button class="btn btn-soft" @click="replyForm.reviewId = null">{{ t('common.cancel') }}</button>
              </div>
            </template>
            <a v-else class="sr-reply-link" @click="openReply(r)">
              {{ r.reply_body ? t('reviews.editReply') : t('reviews.reply') }}
            </a>
          </div>
        </div>

        <div v-if="summary.limits" class="card plan">
          <div class="plan-head">
            <b>{{ t('plan.title') }}: {{ summary.limits.plan === 'pro' ? 'Pro' : t('plan.free') }}</b>
            <span v-if="!summary.limits.enforced" class="muted">{{ t('plan.limitsOff') }}</span>
          </div>
          <div class="plan-row">
            <span>{{ t('plan.productsRow') }}</span>
            <span>{{ summary.limits.products_used }}{{ summary.limits.products_cap ? ` ${t('plan.ofN', { n: summary.limits.products_cap })}` : '' }}</span>
          </div>
          <div class="plan-row">
            <span>{{ t('plan.servicesRow') }}</span>
            <span>{{ summary.limits.services_used }}{{ summary.limits.services_cap ? ` ${t('plan.ofN', { n: summary.limits.services_cap })}` : '' }}</span>
          </div>
          <div class="plan-row">
            <span>{{ t('plan.mailingRow') }}</span>
            <span>{{ summary.limits.mailing_recipients_cap ? t('plan.upToN', { n: summary.limits.mailing_recipients_cap }) : t('plan.unlimited') }}</span>
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
.controls { display: flex; gap: 8px; align-items: center; }
.icon-btn {
  width: 42px; height: 42px; border-radius: 13px; border: 0; background: var(--surface2);
  color: var(--text); display: flex; align-items: center; justify-content: center;
  cursor: pointer; font-size: 18px; line-height: 1;
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
.row-left { display: flex; align-items: center; gap: 10px; min-width: 0; }
.prod-img {
  width: 46px; height: 46px; border-radius: 12px; object-fit: cover;
  background: var(--surface2); flex-shrink: 0;
}
.prod-ph {
  display: inline-flex; align-items: center; justify-content: center; font-size: 24px;
}
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
.delivery {
  display: flex; flex-direction: column; gap: 2px;
  background: var(--surface2); border-radius: 10px;
  padding: 8px 10px; margin-top: 8px; font-size: 13px;
  b { font-size: 11px; letter-spacing: .06em; text-transform: uppercase; color: var(--sub); }
  span { word-break: break-word; }
}
.items {
  display: flex; flex-direction: column; gap: 5px;
  border-top: 1px solid var(--surface2); border-bottom: 1px solid var(--surface2);
  padding: 8px 0;
}
.item { display: flex; justify-content: space-between; gap: 10px; font-size: 13px; }
.item span:first-child { min-width: 0; }
.fulfill-btn { height: 42px; }
.chat-btn { height: 42px; margin-top: 2px; }
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
.reviews-block { margin-top: 12px; display: flex; flex-direction: column; gap: 10px; }
.seller-review { border-top: 1px solid var(--surface2); padding-top: 8px; }
.sr-head { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
.stars { color: #f59e1b; letter-spacing: 1.5px; font-size: 13px; flex-shrink: 0; }
.sr-title { font-size: 12.5px; font-weight: 700; text-align: right; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.seller-review p { margin: 4px 0 0; font-size: 13.5px; line-height: 1.45; }
.sr-reply { margin-top: 6px; border-radius: 10px; background: var(--accent-soft); padding: 8px 10px; }
.sr-reply b { font-size: 11.5px; color: var(--accent); }
.sr-reply p { margin: 3px 0 0; font-size: 13px; line-height: 1.45; }
.sr-reply-link {
  display: inline-block;
  margin-top: 6px;
  color: var(--accent);
  font-size: 12.5px;
  font-weight: 700;
  cursor: pointer;
}
.reply-input {
  resize: none;
  margin-top: 6px;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 8px 10px;
  font-size: 13px;
  font-family: inherit;
  background: var(--surface);
  color: var(--text);
}
.reply-error { color: var(--red); font-size: 12px; margin: 4px 0 0; }
.plan { margin-top: 12px; display: flex; flex-direction: column; gap: 9px; }
.plan-head { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
.plan-head .muted { font-size: 12px; }
.plan-row { display: flex; justify-content: space-between; font-size: 14px; }
.plan-row span:first-child { color: var(--sub); font-weight: 700; }
.plan .hint { margin: 2px 0 0; font-size: 12px; line-height: 1.45; color: var(--sub); }

/* Кошелёк: крупная сумма, под ней статус, потом действие */
.wallet { margin-top: 12px; display: flex; flex-direction: column; gap: 0; }
.wallet-label { font-size: 13px; font-weight: 700; color: var(--sub); }
.wallet-sum { display: flex; align-items: baseline; gap: 6px; margin-top: 6px; }
.wallet-sum b { font-size: 34px; line-height: 1.1; letter-spacing: -0.5px; }
.wallet-sum span { font-size: 15px; font-weight: 700; color: var(--sub); }
.wallet-state { margin: 4px 0 0; font-size: 13px; font-weight: 700; }
.wallet-state.ready { color: var(--green-text); }
.wallet-state.wait { color: var(--sub); }
.wallet-btn { width: 100%; height: 46px; margin-top: 14px; font-size: 15px; }
.wallet-note { margin: 8px 0 0; font-size: 13px; font-weight: 700; color: var(--green-text); }
.wallet-note.err { color: var(--red); }
.wallet-rows {
  display: flex; flex-direction: column; gap: 8px;
  margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--border);
}
.wallet .hint { margin: 10px 0 0; font-size: 12px; line-height: 1.45; color: var(--sub); }
.empty { text-align: center; color: var(--sub); margin-top: 24px; }
.error { text-align: center; color: var(--red); margin-top: 40px; }
.error-line { color: var(--red); font-size: 13px; font-weight: 600; margin: 0 0 10px; }
</style>
