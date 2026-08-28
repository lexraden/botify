<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  approveReview,
  deleteProduct,
  deleteShopLogo,
  fetchMe,
  fetchProducts,
  fetchShopOrders,
  fetchShopStats,
  fetchShopSummary,
  fetchSellerReviews,
  fulfillOrder,
  rejectReview,
  replyToReview,
  sendOrderChatPhoto,
  updateShopName,
  uploadShopLogo,
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

// модерация отзывов: низкие оценки ждут одобрения (порог и автопубликацию
// считает бэкенд). Одобрить публикует, скрыть прячет до правки покупателем.
async function moderateReview(r, action) {
  try {
    const updated = action === 'approve'
      ? await approveReview(botId.value, r.id)
      : await rejectReview(botId.value, r.id)
    reviews.value = reviews.value.map((x) => (x.id === updated.id ? updated : x))
  } catch (e) {
    actionError.value = e.response?.data?.detail || t('reviews.moderateError')
  }
}

// вкладка восстанавливается из ?tab= — возврат из чата заказа открывает заказы
const tab = ref(['products', 'orders', 'reviews', 'stats'].includes(route.query.tab)
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

// роли в магазине (summary.viewer_role): админ ведёт всё, кроме денег, —
// кошелёк и баланс кассы ему не показываем
const isOwner = computed(() => summary.value?.viewer_role !== 'admin')

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
// Отправить можно оплаченный заказ; после отправки кнопка исчезает —
// остаётся чат с покупателем (трек и фото уже в истории чата).
const FULFILLABLE = ['paid']
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

// что продавец отправил при выполнении — одной строкой для карточки.
// Новый формат fulfillment {value, photos}; старые заказы хранят tracking/url/note
const fulfillmentLine = (f) => {
  if (!f) return ''
  const photos = f.photos ? t('seller.photosCount', { n: f.photos }) : ''
  if (f.value) return photos ? `${f.value} · ${photos}` : f.value
  // отправка без трека, одними фото: раньше строка выходила пустой и в
  // карточке оставалось голое «📤» — продавец не видел, что именно отправил
  if (photos) return photos
  return [
    f.tracking ? t('fulfill.tracking', { v: f.tracking }) : '',
    f.url ? t('fulfill.url', { v: f.url }) : '',
    f.note || '',
  ]
    .filter(Boolean)
    .join(' · ')
}

async function reload() {
  const id = botId.value
  ;[summary.value, stats.value, products.value, orders.value] =
    await Promise.all([
      fetchShopSummary(id),
      fetchShopStats(id),
      fetchProducts(id),
      fetchShopOrders(id),
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

// Отправка физического заказа: одно поле «трек или ссылка» плюс до 3 фото
// посылки. Фото уезжают в чат заказа (покупатель получит их от бота) после
// того, как сам fulfill принял сервер.
const MAX_FULFILL_PHOTOS = 3
// как у фото товара и лого магазина: тяжёлое молча не берём
const MAX_FULFILL_MB = 5

const fulfillPhotoInput = ref(null)
const fulfillForm = ref({ orderId: null, value: '', photos: [], sending: false })

function openFulfill(o) {
  revokePhotos(fulfillForm.value.photos)
  fulfillForm.value = { orderId: o.id, value: '', photos: [], sending: false }
}

// file → URL.createObjectURL для превью; чистим за собой, иначе утекаем
function revokePhotos(photos) {
  for (const p of photos) URL.revokeObjectURL(p.url)
}

function pickFulfillPhotos() {
  // input лежит внутри v-for по заказам, поэтому Vue отдаёт ref массивом,
  // даже когда форма открыта одна — кликать нужно по элементу
  const el = Array.isArray(fulfillPhotoInput.value) ? fulfillPhotoInput.value[0] : fulfillPhotoInput.value
  el?.click()
}

function onFulfillPhotos(e) {
  // файлы читаем ДО сброса: value='' в браузере очищает выбранные файлы
  const files = Array.from(e.target.files ?? [])
  e.target.value = '' // повторный выбор того же файла должен срабатывать
  if (!files.length) return
  const form = fulfillForm.value
  const overflow = MAX_FULFILL_PHOTOS - form.photos.length
  if (overflow <= 0) return
  for (const file of files.slice(0, overflow)) {
    if (file.size > MAX_FULFILL_MB * 1024 * 1024) {
      // молча пропущенное фото выглядит как «кнопка не работает»
      actionError.value = t('form.fileTooBig', { n: MAX_FULFILL_MB })
      continue
    }
    form.photos.push({ file, url: URL.createObjectURL(file) })
  }
}

function dropPhoto(i) {
  const form = fulfillForm.value
  URL.revokeObjectURL(form.photos[i].url)
  form.photos.splice(i, 1)
}

async function submitFulfill() {
  const f = fulfillForm.value
  if (f.sending || !(f.value.trim() || f.photos.length)) return
  f.sending = true
  actionError.value = ''
  try {
    await fulfillOrder(botId.value, f.orderId, {
      value: f.value.trim() || null,
      photos: f.photos.length,
    })
    // Фото — следом за fulfill; сбой одного не отменяет отправку заказа.
    // Но покупателю уже ушёл пуш «Фото посылки ниже (N шт.)», а форма
    // отправки после fulfill исчезает — если промолчать, продавец не узнает,
    // что дослать нечего, и покупатель останется с обещанием без фото.
    let failed = 0
    for (const p of f.photos) {
      try {
        await sendOrderChatPhoto(botId.value, f.orderId, p.file, '')
      } catch {
        failed += 1
      }
    }
    revokePhotos(f.photos)
    fulfillForm.value.orderId = null
    await reload()
    if (failed) actionError.value = t('seller.photosFailed', { n: failed })
  } catch (e) {
    actionError.value = e.response?.data?.detail || t('seller.fulfillError')
  } finally {
    f.sending = false
  }
}

// --- идентичность магазина в шапке витрины: показное имя и логотип ---
// Панель открывается кликом по аватарке в шапке кабинета. Лого уезжает на
// сервер сразу после выбора файла (как фото товара), имя — по кнопке.
const MAX_LOGO_MB = 5

const identityOpen = ref(false)
const shopName = ref('')
const savingName = ref(false)
const nameError = ref('')
const uploadingLogo = ref(false)
const logoError = ref('')
const logoInput = ref(null)

// буква аватара: от показного имени, без него — от юзернейма бота
const identityLetter = computed(() => {
  const base = summary.value?.shop_name || summary.value?.bot_username || ''
  return base.charAt(0).toUpperCase()
})

function toggleIdentity() {
  if (!identityOpen.value) {
    // префилл при каждом открытии: актуальные значения summary уже загружены
    shopName.value = summary.value?.shop_name ?? ''
    nameError.value = ''
    logoError.value = ''
  }
  identityOpen.value = !identityOpen.value
}

async function saveIdentity() {
  if (savingName.value) return
  const name = shopName.value.trim()
  if (!name) {
    // пустая строка на сервере — ошибка: сброс на дефолт из UI не делаем,
    // чтобы случайная очистка поля не стёрла название магазина
    nameError.value = t('seller.identity.nameRequired')
    return
  }
  savingName.value = true
  try {
    await updateShopName(botId.value, name)
    summary.value = await fetchShopSummary(botId.value)
    identityOpen.value = false
  } catch (e) {
    nameError.value = e.response?.data?.detail || t('form.saveError')
  } finally {
    savingName.value = false
  }
}

async function onPickLogo(e) {
  const file = e.target.files?.[0]
  e.target.value = '' // повторный выбор того же файла должен срабатывать
  if (!file || uploadingLogo.value) return
  logoError.value = ''
  if (file.size > MAX_LOGO_MB * 1024 * 1024) {
    logoError.value = t('form.fileTooBig', { n: MAX_LOGO_MB })
    return
  }
  uploadingLogo.value = true
  try {
    await uploadShopLogo(botId.value, file)
    summary.value = await fetchShopSummary(botId.value)
  } catch (err) {
    logoError.value = err.response?.data?.detail || t('form.uploadError')
  } finally {
    uploadingLogo.value = false
  }
}

async function removeLogo() {
  if (uploadingLogo.value) return
  uploadingLogo.value = true
  logoError.value = ''
  try {
    await deleteShopLogo(botId.value)
    summary.value = await fetchShopSummary(botId.value)
  } catch (e) {
    logoError.value = e.response?.data?.detail || t('form.uploadError')
  } finally {
    uploadingLogo.value = false
  }
}
</script>

<template>
  <div class="shop">
    <p v-if="error" class="error">{{ error }}</p>
    <template v-else-if="summary">
      <header>
        <!-- аватар-кнопка открывает панель идентичности: так продавец меняет
             имя и лого, которые покупатели видят в шапке витрины -->
        <div class="title">
          <button class="avatar-btn" :aria-label="t('seller.identity.toggle')" @click="toggleIdentity">
            <img
              v-if="summary.logo_url"
              class="shop-avatar"
              :src="summary.logo_url"
              :alt="summary.shop_name || summary.bot_username"
            />
            <span v-else class="shop-avatar letter">{{ identityLetter }}</span>
          </button>
          <div class="title-text">
            <h2>{{ t('seller.shop') }}</h2>
            <div class="bot-line">
              <span class="dot" :class="{ off: !summary.is_active }" />
              <span>@{{ summary.bot_username }}</span>
            </div>
          </div>
        </div>
        <!-- рассылки и профиль продавца: магазины, язык, тема. Системную
             «Назад» Telegram рисует сам (services/backButton.js), дубль в
             шапке не нужен -->
        <div class="controls">
          <button class="icon-btn" :aria-label="t('mailings.title')" @click="router.push(`/shop/${botId}/mailings`)">
            <svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">
              <path d="m3 11 18-5v12L3 13v-2z" />
              <path d="M11.6 16.8a3 3 0 1 1-5.8-1.6" />
            </svg>
          </button>
          <button class="icon-btn" :aria-label="t('seller.profileTitle')" @click="router.push(`/shop/${botId}/profile`)">
            <svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="8" r="4" />
              <path d="M4.5 20a7.5 7.5 0 0 1 15 0" />
            </svg>
          </button>
        </div>
      </header>

      <!-- панель идентичности: превью аватара, лого грузится сразу после
           выбора файла, название сохраняется кнопкой -->
      <div v-if="identityOpen" class="card identity">
        <b class="id-title">{{ t('seller.identity.title') }}</b>
        <p class="id-hint">{{ t('seller.identity.hint') }}</p>
        <div class="identity-row">
          <img v-if="summary.logo_url" class="preview-avatar" :src="summary.logo_url" alt="" />
          <span v-else class="preview-avatar letter">{{ identityLetter }}</span>
          <div class="logo-actions">
            <input
              ref="logoInput"
              type="file"
              accept="image/jpeg,image/png,image/webp,image/gif"
              hidden
              @change="onPickLogo"
            />
            <button class="btn btn-soft act" type="button" :disabled="uploadingLogo" @click="logoInput.click()">
              {{ uploadingLogo ? '…' : (summary.logo_url ? t('seller.identity.replaceLogo') : t('seller.identity.uploadLogo')) }}
            </button>
            <button
              v-if="summary.logo_url"
              class="btn btn-soft act"
              type="button"
              :disabled="uploadingLogo"
              @click="removeLogo"
            >
              {{ t('seller.identity.removeLogo') }}
            </button>
          </div>
        </div>
        <p v-if="logoError" class="id-error">{{ logoError }}</p>

        <label for="shop-name-input">{{ t('seller.identity.nameLabel') }}</label>
        <input
          id="shop-name-input"
          v-model="shopName"
          type="text"
          maxlength="64"
          :placeholder="'@' + (summary.bot_username || '')"
        />
        <p v-if="nameError" class="id-error">{{ nameError }}</p>
        <button
          class="btn btn-primary save-btn"
          :disabled="savingName || !shopName.trim()"
          @click="saveIdentity"
        >
          {{ savingName ? '…' : t('form.save') }}
        </button>
      </div>

      <div class="stats">
        <div class="card stat">
          <b class="num">{{ summary.customers_count }}</b><span>{{ t('stat.customers') }}</span>
        </div>
        <div class="card stat">
          <b class="num">{{ summary.orders_count }}</b><span>{{ t('stat.orders') }}</span>
        </div>
        <div v-if="isOwner" class="card stat green">
          <b class="num">{{ balance.toFixed(2) }}</b><span>{{ t('wallet.balanceShort') }}</span>
        </div>
      </div>

      <nav>
        <button :class="{ active: tab === 'products' }" @click="tab = 'products'">{{ t('tab.products') }}</button>
        <button :class="{ active: tab === 'orders' }" @click="tab = 'orders'">{{ t('tab.orders') }}</button>
        <button :class="{ active: tab === 'reviews' }" @click="tab = 'reviews'">{{ t('tab.reviews') }}</button>
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
          <!-- адрес нужен, чтобы отправить: показываем отдельным блоком.
               Имя/телефон покупателя больше не собираем — у старых заказов есть -->
          <div v-if="o.delivery" class="delivery">
            <b>{{ t('seller.deliveryTitle') }}</b>
            <span v-if="o.delivery.name || o.delivery.phone">
              {{ [o.delivery.name, o.delivery.phone].filter(Boolean).join(' · ') }}
            </span>
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
          <!-- фото посылки: до трёх квадратиков с превью; клик по пустому
               «+» открывает выбор файлов -->
          <div v-if="fulfillForm.orderId === o.id" class="fulfill-form">
            <div class="photo-tiles">
              <div
                v-for="(p, i) in fulfillForm.photos"
                :key="p.url"
                class="tile filled"
              >
                <img :src="p.url" alt="" />
                <button class="drop" type="button" :aria-label="t('orders.delete')" @click="dropPhoto(i)">✕</button>
              </div>
              <button
                v-if="fulfillForm.photos.length < MAX_FULFILL_PHOTOS"
                class="tile add"
                type="button"
                :aria-label="t('chat.attachPhoto')"
                :disabled="fulfillForm.sending"
                @click="pickFulfillPhotos"
              >
                +
              </button>
            </div>
            <input ref="fulfillPhotoInput" type="file" accept="image/jpeg,image/png,image/webp,image/gif" multiple hidden @change="onFulfillPhotos" />
            <input
              v-model="fulfillForm.value"
              maxlength="512"
              :placeholder="t('seller.fulfillValuePh')"
            />
            <div class="pair">
              <button class="btn btn-soft" @click="fulfillForm.orderId = null">{{ t('common.cancel') }}</button>
              <button
                class="btn btn-green"
                :disabled="fulfillForm.sending || !(fulfillForm.value.trim() || fulfillForm.photos.length)"
                @click="submitFulfill"
              >
                {{ fulfillForm.sending ? '…' : t('seller.send') }}
              </button>
            </div>
          </div>
        </div>
        <p v-if="!orders.length" class="empty">{{ t('seller.noOrders') }}</p>
      </template>

      <template v-else-if="tab === 'reviews'">
        <!-- что говорят покупатели: личность не раскрывается, только псевдоним.
             Низкие оценки ждут одобрения, скрытые видны только здесь -->
        <p v-if="!reviews.length" class="empty">{{ t('seller.noReviews') }}</p>
        <div v-else class="card reviews-block">
          <div v-for="r in reviews" :key="r.id" class="seller-review">
            <div class="sr-head">
              <!-- слева имя со звёздами; справа колонкой — заказ, под ним товар -->
              <span class="stars"><template v-if="r.author_name">{{ r.author_name }} · </template>{{ '★'.repeat(r.rating) }}</span>
              <span class="sr-right">
                <span class="muted sr-order">{{ t('reviews.orderLabel', { n: r.order_id }) }}</span>
                <span class="sr-meta">{{ r.product_title }}</span>
              </span>
            </div>
            <p v-if="r.body">{{ r.body }}</p>
            <p v-if="r.status !== 'published'" class="sr-status" :class="r.status">
              {{ r.status === 'pending' ? t('reviews.statusPending') : t('reviews.statusRejected') }}
            </p>

            <div v-if="r.status !== 'published'" class="mod-actions">
              <button
                v-if="r.status === 'pending'"
                class="btn btn-soft mod"
                :aria-label="t('reviews.reject')"
                @click="moderateReview(r, 'reject')"
              >
                {{ t('reviews.reject') }}
              </button>
              <button class="btn btn-green mod" @click="moderateReview(r, 'approve')">
                {{ r.status === 'pending' ? t('reviews.approve') : t('reviews.publish') }}
              </button>
            </div>

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

        <!-- кошелёк — только владельцу: админ видит магазин, но не кассу -->
        <div v-if="isOwner" class="card wallet">
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
.title { display: flex; align-items: center; gap: 10px; min-width: 0; }
.title-text { min-width: 0; }
.avatar-btn {
  border: 0; background: none; padding: 0; cursor: pointer;
  border-radius: 50%; flex-shrink: 0;
}
.shop-avatar { width: 46px; height: 46px; border-radius: 50%; object-fit: cover; }
.shop-avatar.letter {
  background: var(--accent); color: #fff;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 20px; font-weight: 800;
}
.bot-line { display: flex; align-items: center; gap: 6px; font-size: 13px; color: var(--sub); }
.dot { width: 8px; height: 8px; border-radius: 50%; background: var(--green); }
.dot.off { background: var(--sub); }
.controls { display: flex; gap: 8px; align-items: center; }
.icon-btn {
  width: 42px; height: 42px; border-radius: 13px; border: 0; background: var(--surface2);
  color: var(--text); display: flex; align-items: center; justify-content: center;
  cursor: pointer; font-size: 18px; line-height: 1;
}
/* Панель идентичности магазина */
.identity { display: flex; flex-direction: column; gap: 10px; margin-bottom: 12px; padding: 14px; }
.id-title { font-size: 15px; }
.id-hint { margin: -5px 0 0; font-size: 12.5px; line-height: 1.45; color: var(--sub); }
.identity-row { display: flex; align-items: center; gap: 12px; }
.preview-avatar { width: 56px; height: 56px; border-radius: 50%; object-fit: cover; flex-shrink: 0; }
.preview-avatar.letter {
  background: var(--accent); color: #fff;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 24px; font-weight: 800;
}
.logo-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.logo-actions .act { height: 40px; padding: 0 14px; font-size: 13.5px; }
.id-error { margin: -4px 0 0; color: var(--red); font-size: 12.5px; }
.identity label { font-size: 12px; color: var(--sub); margin-top: 2px; font-weight: 700; }
.save-btn { margin-top: 4px; }

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
.photo-tiles { display: flex; gap: 8px; }
.tile {
  width: 64px; height: 64px; border-radius: 12px; padding: 0;
  border: 1px solid var(--line); background: var(--surface2);
  position: relative; overflow: visible; cursor: pointer;
}
.tile.add {
  font-size: 26px; color: var(--sub); line-height: 1;
  display: flex; align-items: center; justify-content: center;
}
.tile.filled img { width: 100%; height: 100%; object-fit: cover; border-radius: inherit; display: block; }
.tile .drop {
  position: absolute; top: -6px; right: -6px; width: 20px; height: 20px;
  border-radius: 50%; border: 0; background: var(--text); color: var(--surface);
  font-size: 11px; line-height: 1; cursor: pointer;
}
.pair { display: flex; gap: 8px; }
.pair .btn { height: 42px; }
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
.sr-right { display: flex; flex-direction: column; align-items: flex-end; min-width: 0; }
.sr-order { font-size: 12.5px; font-weight: 700; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.seller-review p { margin: 4px 0 0; font-size: 13.5px; line-height: 1.45; }
.sr-meta { font-size: 12.5px; color: var(--sub); max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sr-status { font-size: 12.5px; font-weight: 700; }
.sr-status.pending { color: var(--accent); }
.sr-status.rejected { color: var(--sub); }
.mod-actions { display: flex; gap: 8px; margin-top: 8px; }
.mod-actions .mod { flex: 1; height: 38px; font-size: 13.5px; }
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
