import axios from 'axios'
import { getBotId, getInitData } from './services/telegram'
import { startLoading, stopLoading } from './services/loading'

const api = axios.create({ baseURL: '/api' })

api.interceptors.request.use((config) => {
  config.headers['X-Init-Data'] = getInitData()
  startLoading()
  return config
})

// Любой ответ снимает запрос со счётчика — оверлей не залипает на ошибке
api.interceptors.response.use(
  (response) => {
    stopLoading()
    return response
  },
  (error) => {
    stopLoading()
    return Promise.reject(error)
  },
)

// --- витрина покупателя (контекст seller-бота из query-параметра) ---
export const fetchShop = () => api.get(`/store/${getBotId()}`).then((r) => r.data)
export const createOrder = (items, comment) =>
  api.post(`/store/${getBotId()}/orders`, { items, comment }).then((r) => r.data)
export const fetchMyOrders = () => api.get(`/store/${getBotId()}/orders/my`).then((r) => r.data)
// отзывы: список у товара, оценка — только по своему доставленному заказу
export const fetchProductReviews = (productId) =>
  api.get(`/store/${getBotId()}/products/${productId}/reviews`).then((r) => r.data)
export const submitOrderReviews = (orderId, items) =>
  api.post(`/store/${getBotId()}/orders/${orderId}/reviews`, { items }).then((r) => r.data)
// Статистика витрины: ошибки глотаем — аналитика не должна ломать покупку
export const trackEvent = (type, productId = null) =>
  api.post(`/store/${getBotId()}/events`, { type, product_id: productId }).catch(() => {})

// --- кабинет продавца (контекст hub-бота) ---
export const fetchMe = () => api.get('/seller/me').then((r) => r.data)
export const acceptTerms = () =>
  api.post('/seller/onboarding/terms-accept').then((r) => r.data)
export const connectBot = (token) => api.post('/seller/bots', { token }).then((r) => r.data)
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
export const uploadProductImage = (botId, file) =>
  api
    .post(`/seller/bots/${botId}/product-image`, file, {
      headers: { 'Content-Type': 'application/octet-stream' },
    })
    .then((r) => r.data)
export const fetchShopOrders = (botId) => api.get(`/seller/bots/${botId}/orders`).then((r) => r.data)
// отзывы о товарах магазина — только чтение, без автора
export const fetchSellerReviews = (botId) =>
  api.get(`/seller/bots/${botId}/reviews`).then((r) => r.data)
export const fulfillOrder = (botId, id, data) =>
  api.post(`/seller/bots/${botId}/orders/${id}/fulfill`, data).then((r) => r.data)
// чат заказа: история читается всегда, писать можно в открытом окне
export const fetchOrderChat = (botId, orderId) =>
  api.get(`/seller/bots/${botId}/orders/${orderId}/chat`).then((r) => r.data)
export const sendOrderChatMessage = (botId, orderId, body) =>
  api.post(`/seller/bots/${botId}/orders/${orderId}/chat/messages`, { body }).then((r) => r.data)
// фото в чат: сырые байты файла (как у фото товара), черновик уезжает подписью
export const sendOrderChatPhoto = (botId, orderId, file, caption) =>
  api
    .post(
      `/seller/bots/${botId}/orders/${orderId}/chat/photo${
        caption ? `?caption=${encodeURIComponent(caption)}` : ''
      }`,
      file,
      { headers: { 'Content-Type': 'application/octet-stream' } },
    )
    .then((r) => r.data)
export const withdrawPayout = (botId) =>
  api.post(`/seller/bots/${botId}/payouts/withdraw`).then((r) => r.data)
export const fetchMailings = (botId) => api.get(`/seller/bots/${botId}/mailings`).then((r) => r.data)
export const createMailing = (botId, data) =>
  api.post(`/seller/bots/${botId}/mailings`, data).then((r) => r.data)
