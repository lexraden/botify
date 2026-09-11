import axios from 'axios'
import { getBotId, getInitData } from './services/telegram'
import { compressImage } from './services/imageCompress'
import { storedLocale } from './services/locale'
import { startLoading, stopLoading } from './services/loading'
import { APP_VERSION } from './services/version'

const api = axios.create({ baseURL: '/api' })

// Полноэкранный оверлей уместен для действий, которых человек ждёт, и вреден
// для фоновых: чат опрашивается раз в 4 секунды, «Мои покупки» — раз в 10, и
// без этого флага экран мигал бы поверх переписки всё время, что она открыта.
const SILENT = { silent: true }

api.interceptors.request.use((config) => {
  config.headers['X-Init-Data'] = getInitData()
  // язык уведомлений на бэкенде = язык Mini App; '' — ручной выбор ещё не сделан
  config.headers['X-Locale'] = storedLocale() ?? ''
  if (!config.silent) startLoading()
  return config
})

// Любой ответ снимает запрос со счётчика — оверлей не залипает на ошибке
api.interceptors.response.use(
  (response) => {
    if (!response.config?.silent) stopLoading()
    return response
  },
  (error) => {
    if (!error.config?.silent) stopLoading()
    return Promise.reject(error)
  },
)

// --- витрина покупателя (контекст seller-бота из query-параметра) ---
export const fetchShop = () => api.get(`/store/${getBotId()}`).then((r) => r.data)
// payment: { method: 'crypto' | 'p2p', methodId } — способ выбирают на чекауте,
// у перевода счёт не выписывается вовсе, вместо ссылки едут реквизиты
export const createOrder = (items, comment, delivery = null, payment = null) =>
  api
    .post(`/store/${getBotId()}/orders`, {
      items,
      comment,
      delivery,
      payment_method: payment?.method || 'crypto',
      payment_method_id: payment?.methodId ?? null,
    })
    .then((r) => r.data)
// «Я оплатил» по переводу: заявка, а не оплата — подтверждает продавец
export const claimOrderPaid = (orderId) =>
  api.post(`/store/${getBotId()}/orders/${orderId}/paid-claim`).then((r) => r.data)
export const fetchMyOrders = (silent = false) =>
  api.get(`/store/${getBotId()}/orders/my`, silent ? SILENT : {}).then((r) => r.data)
// неоплаченный заказ: свежая ссылка на оплату или отмена покупателем
export const payOrder = (orderId) =>
  api.post(`/store/${getBotId()}/orders/${orderId}/pay`).then((r) => r.data)
export const cancelOrder = (orderId) =>
  api.post(`/store/${getBotId()}/orders/${orderId}/cancel`).then((r) => r.data)
// «Доставлен» ставит покупатель: отправка и получение — разные события
export const confirmReceived = (orderId) =>
  api.post(`/store/${getBotId()}/orders/${orderId}/received`).then((r) => r.data)
// отзывы: список у товара, оценка — только по своему доставленному заказу
export const fetchProductReviews = (productId) =>
  api.get(`/store/${getBotId()}/products/${productId}/reviews`).then((r) => r.data)
export const submitOrderReviews = (orderId, items) =>
  api.post(`/store/${getBotId()}/orders/${orderId}/reviews`, { items }).then((r) => r.data)
// передумал: свой отзыв позиции можно снять целиком
export const deleteOrderReview = (orderId, productId) =>
  api.delete(`/store/${getBotId()}/orders/${orderId}/reviews/${productId}`).then((r) => r.data)
// Статистика витрины: ошибки глотаем — аналитика не должна ломать покупку
export const trackEvent = (type, productId = null) =>
  api.post(`/store/${getBotId()}/events`, { type, product_id: productId }, SILENT).catch(() => {})
// «Связаться с нами»: обращение платформе, а не продавцу. Контекст (кто,
// какой магазин) бэкенд добавит сам; отсюда — тип, текст, экран и версия.
export const sendBuyerFeedback = (type, message, screen) =>
  api
    .post(`/store/${getBotId()}/feedback`, { type, message, screen, app_version: APP_VERSION })
    .then((r) => r.data)
// Профиль покупателя: своё имя. Пустая строка — сброс к имени из Telegram.
export const fetchBuyerMe = () => api.get(`/store/${getBotId()}/me`).then((r) => r.data)
export const updateBuyerName = (name) =>
  api.patch(`/store/${getBotId()}/me`, { name }).then((r) => r.data)

// --- кабинет продавца (контекст hub-бота) ---
export const fetchMe = () => api.get('/seller/me').then((r) => r.data)
export const acceptTerms = () =>
  api.post('/seller/onboarding/terms-accept').then((r) => r.data)
export const connectBot = (token) => api.post('/seller/bots', { token }).then((r) => r.data)
// «Связаться с нами» из кабинета: тот же канал, что у покупателей, но от
// продавца и с магазином из адреса
export const sendSellerFeedback = (botId, type, message, screen) =>
  api
    .post(`/seller/bots/${botId}/feedback`, { type, message, screen, app_version: APP_VERSION })
    .then((r) => r.data)
// управление магазином прямо из кабинета; каждое действие дублируется в hub-бот
export const disableShop = (botId) =>
  api.post(`/seller/bots/${botId}/disable`).then((r) => r.data)
export const enableShop = (botId) =>
  api.post(`/seller/bots/${botId}/enable`).then((r) => r.data)
export const deleteShop = (botId) => api.delete(`/seller/bots/${botId}`).then((r) => r.data)


// --- всё ниже — в контексте конкретного магазина (bot_id) ---
export const fetchShopSummary = (botId) =>
  api.get(`/seller/bots/${botId}/summary`).then((r) => r.data)
export const fetchShopStats = (botId) => api.get(`/seller/bots/${botId}/stats`).then((r) => r.data)
// идентичность магазина в шапке витрины: показное имя и логотип
export const updateShopName = (botId, name) =>
  api.put(`/seller/bots/${botId}/shop-name`, { shop_name: name }).then((r) => r.data)
// лого: сырые байты файла, тип сервер определяет по содержимому
export const uploadShopLogo = async (botId, file) =>
  api
    .post(`/seller/bots/${botId}/shop-logo`, await compressImage(file), {
      headers: { 'Content-Type': 'application/octet-stream' },
    })
    .then((r) => r.data)
export const deleteShopLogo = (botId) =>
  api.delete(`/seller/bots/${botId}/shop-logo`).then((r) => r.data)
export const fetchProducts = (botId) =>
  api.get(`/seller/bots/${botId}/products`).then((r) => r.data)
export const saveProduct = (botId, product) =>
  (product.id
    ? api.put(`/seller/bots/${botId}/products/${product.id}`, product)
    : api.post(`/seller/bots/${botId}/products`, product)
  ).then((r) => r.data)
export const deleteProduct = (botId, id) =>
  api.delete(`/seller/bots/${botId}/products/${id}`).then((r) => r.data)
// фото товара: сырые байты файла, тип сервер определяет по содержимому
export const uploadProductImage = async (botId, file) =>
  api
    .post(`/seller/bots/${botId}/product-image`, await compressImage(file), {
      headers: { 'Content-Type': 'application/octet-stream' },
    })
    .then((r) => r.data)
export const fetchShopOrders = (botId) => api.get(`/seller/bots/${botId}/orders`).then((r) => r.data)
// отзывы о товарах магазина; на каждый продавец может ответить один раз
export const fetchSellerReviews = (botId) =>
  api.get(`/seller/bots/${botId}/reviews`).then((r) => r.data)
// повторная отправка правит ответ
export const replyToReview = (botId, reviewId, body) =>
  api.post(`/seller/bots/${botId}/reviews/${reviewId}/reply`, { body }).then((r) => r.data)
// модерация: одобрить публикует, скрыть убирает из витрины (до правки покупателем)
export const approveReview = (botId, reviewId) =>
  api.post(`/seller/bots/${botId}/reviews/${reviewId}/approve`).then((r) => r.data)
export const rejectReview = (botId, reviewId) =>
  api.post(`/seller/bots/${botId}/reviews/${reviewId}/reject`).then((r) => r.data)
// Pro/Plus: состояние тарифа и счёт на оплату. Тариф общий на продавца,
// поэтому адрес без bot_id — в отличие от всего остального в кабинете.
export const fetchSubscription = () =>
  api.get('/seller/subscription').then((r) => r.data)
export const createSubscriptionInvoice = (method, plan) =>
  api.post('/seller/subscription/invoice', { method, plan }).then((r) => r.data)
// Реквизиты магазина для приёма переводов (тариф Pro). Только владелец:
// переводы идут на его счёт, а не на счёт приглашённого админа.
export const fetchPaymentMethods = (botId) =>
  api.get(`/seller/bots/${botId}/payment-methods`).then((r) => r.data)
export const savePaymentMethod = (botId, method) =>
  (method.id
    ? api.put(`/seller/bots/${botId}/payment-methods/${method.id}`, method)
    : api.post(`/seller/bots/${botId}/payment-methods`, method)
  ).then((r) => r.data)
export const deletePaymentMethod = (botId, id) =>
  api.delete(`/seller/bots/${botId}/payment-methods/${id}`).then((r) => r.data)
// Подтверждение перевода продавцом — единственный способ оплатить p2p-заказ
export const confirmOrderPayment = (botId, orderId) =>
  api.post(`/seller/bots/${botId}/orders/${orderId}/confirm-payment`).then((r) => r.data)
export const rejectOrderPayment = (botId, orderId) =>
  api.post(`/seller/bots/${botId}/orders/${orderId}/reject-payment`).then((r) => r.data)
export const fulfillOrder = (botId, id, data) =>
  api.post(`/seller/bots/${botId}/orders/${id}/fulfill`, data).then((r) => r.data)
// Переписки магазина: заказ, превью последнего сообщения и сколько новых.
// Отдельный адрес, а не поле в summary: инбокс опрашивается чаще кабинета.
export const fetchShopChats = (botId) =>
  api.get(`/seller/bots/${botId}/chats`).then((r) => r.data)

// Чат заказа со стороны покупателя. Тот же тред, что видит продавец, только
// адресуется своим заказом, а не парой «магазин + заказ»: магазин покупателя
// уже определён bot_id, а чужой заказ бэкенд отдаёт 403.
export const fetchMyOrderChat = (orderId, silent = false) =>
  api
    .get(`/store/${getBotId()}/orders/${orderId}/chat`, silent ? SILENT : {})
    .then((r) => r.data)
export const sendMyOrderChatMessage = (orderId, body) =>
  api
    .post(`/store/${getBotId()}/orders/${orderId}/chat/messages`, { body })
    .then((r) => r.data)
// Фото покупателя в чат заказа — тот же приём сырых байтов, что и у продавца.
// Понадобилось для оплаты переводом: чек показывают здесь, а не «куда-нибудь».
export const sendMyOrderChatPhoto = async (orderId, file, caption) =>
  api
    .post(
      `/store/${getBotId()}/orders/${orderId}/chat/photo${
        caption ? `?caption=${encodeURIComponent(caption)}` : ''
      }`,
      await compressImage(file),
      { headers: { 'Content-Type': 'application/octet-stream' } },
    )
    .then((r) => r.data)

// чат заказа: история читается всегда, писать можно в открытом окне
export const fetchOrderChat = (botId, orderId, silent = false) =>
  api.get(`/seller/bots/${botId}/orders/${orderId}/chat`, silent ? SILENT : {}).then((r) => r.data)
export const sendOrderChatMessage = (botId, orderId, body) =>
  api.post(`/seller/bots/${botId}/orders/${orderId}/chat/messages`, { body }).then((r) => r.data)
// фото в чат: сырые байты файла (как у фото товара), черновик уезжает подписью
export const sendOrderChatPhoto = async (botId, orderId, file, caption) =>
  api
    .post(
      `/seller/bots/${botId}/orders/${orderId}/chat/photo${
        caption ? `?caption=${encodeURIComponent(caption)}` : ''
      }`,
      await compressImage(file),
      { headers: { 'Content-Type': 'application/octet-stream' } },
    )
    .then((r) => r.data)
export const withdrawPayout = (botId) =>
  api.post(`/seller/bots/${botId}/payouts/withdraw`).then((r) => r.data)
export const fetchMailings = (botId) => api.get(`/seller/bots/${botId}/mailings`).then((r) => r.data)
export const createMailing = (botId, data) =>
  api.post(`/seller/bots/${botId}/mailings`, data).then((r) => r.data)
