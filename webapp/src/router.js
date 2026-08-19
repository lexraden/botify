import { createRouter, createWebHistory } from 'vue-router'
import { getBotId } from './services/telegram'
import StoreView from './views/StoreView.vue'
import CheckoutView from './views/CheckoutView.vue'
import MyOrdersView from './views/MyOrdersView.vue'
import SellerView from './views/SellerView.vue'
import ProductFormView from './views/ProductFormView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    // покупатель (открыто из seller-бота, есть ?bot_id=)
    { path: '/', name: 'store', component: StoreView },
    { path: '/checkout', name: 'checkout', component: CheckoutView },
    { path: '/my-orders', name: 'my-orders', component: MyOrdersView },
    // продавец (открыто из hub-бота)
    { path: '/seller', name: 'seller', component: SellerView },
    { path: '/seller/product/:id?', name: 'product-form', component: ProductFormView },
  ],
})

// без bot_id это кабинет продавца
router.beforeEach((to) => {
  if (to.name === 'store' && !getBotId()) return { name: 'seller' }
  return true
})

export default router
