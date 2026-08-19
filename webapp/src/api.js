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

// --- кабинет продавца (контекст hub-бота) ---
export const fetchMe = () => api.get('/seller/me').then((r) => r.data)
export const confirmPayment = () => api.post('/seller/onboarding/payment-done').then((r) => r.data)
export const connectBot = (token) => api.post('/seller/bots', { token }).then((r) => r.data)

// --- всё ниже — в контексте конкретного магазина (bot_id) ---
export const fetchShopSummary = (botId) =>
  api.get(`/seller/bots/${botId}/summary`).then((r) => r.data)
export const fetchProducts = (botId) =>
  api.get(`/seller/bots/${botId}/products`).then((r) => r.data)
export const saveProduct = (botId, product) =>
  (product.id
    ? api.put(`/seller/bots/${botId}/products/${product.id}`, product)
    : api.post(`/seller/bots/${botId}/products`, product)
  ).then((r) => r.data)
export const deleteProduct = (botId, id) =>
  api.delete(`/seller/bots/${botId}/products/${id}`).then((r) => r.data)
export const fetchShopOrders = (botId) => api.get(`/seller/bots/${botId}/orders`).then((r) => r.data)
export const fulfillOrder = (botId, id, data) =>
  api.post(`/seller/bots/${botId}/orders/${id}/fulfill`, data).then((r) => r.data)
export const fetchMailings = (botId) => api.get(`/seller/bots/${botId}/mailings`).then((r) => r.data)
export const createMailing = (botId, data) =>
  api.post(`/seller/bots/${botId}/mailings`, data).then((r) => r.data)
