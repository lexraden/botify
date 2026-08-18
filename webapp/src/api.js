import axios from 'axios'
import { getBotId, getInitData } from './services/telegram'

const api = axios.create({ baseURL: '/api' })

api.interceptors.request.use((config) => {
  config.headers['X-Init-Data'] = getInitData()
  return config
})

// --- витрина (контекст seller-бота) ---
export const fetchShop = () => api.get(`/store/${getBotId()}`).then((r) => r.data)
export const createOrder = (items, comment) =>
  api.post(`/store/${getBotId()}/orders`, { items, comment }).then((r) => r.data)
export const fetchMyOrders = () => api.get(`/store/${getBotId()}/orders/my`).then((r) => r.data)

// --- кабинет продавца (контекст hub-бота) ---
export const fetchMe = () => api.get('/seller/me').then((r) => r.data)
export const fetchProducts = () => api.get('/seller/products').then((r) => r.data)
export const saveProduct = (product) =>
  (product.id
    ? api.put(`/seller/products/${product.id}`, product)
    : api.post('/seller/products', product)
  ).then((r) => r.data)
export const deleteProduct = (id) => api.delete(`/seller/products/${id}`).then((r) => r.data)
export const fetchSellerOrders = () => api.get('/seller/orders').then((r) => r.data)
export const fulfillOrder = (id, data) =>
  api.post(`/seller/orders/${id}/fulfill`, data).then((r) => r.data)
export const fetchMailings = () => api.get('/seller/mailings').then((r) => r.data)
export const createMailing = (data) => api.post('/seller/mailings', data).then((r) => r.data)
