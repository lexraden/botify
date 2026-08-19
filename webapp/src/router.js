import { createRouter, createWebHistory } from 'vue-router'
import { getBotId } from './services/telegram'
import { fetchMe } from './api'

import StoreView from './views/StoreView.vue'
import CheckoutView from './views/CheckoutView.vue'
import MyOrdersView from './views/MyOrdersView.vue'
import OnboardingPayment from './views/OnboardingPayment.vue'
import OnboardingBot from './views/OnboardingBot.vue'
import ShopsView from './views/ShopsView.vue'
import ShopView from './views/ShopView.vue'
import ProductFormView from './views/ProductFormView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    // покупатель — Mini App открыт из seller-бота (есть ?bot_id=)
    { path: '/', name: 'store', component: StoreView },
    { path: '/checkout', component: CheckoutView },
    { path: '/my-orders', name: 'my-orders', component: MyOrdersView },
    // продавец — Mini App открыт из hub-бота
    { path: '/onboarding/payment', component: OnboardingPayment },
    { path: '/onboarding/bot', component: OnboardingBot },
    { path: '/shops', component: ShopsView },
    { path: '/shop/:botId', component: ShopView },
    { path: '/shop/:botId/product/:id?', component: ProductFormView },
  ],
})

// Куда отправить продавца при открытии приложения. Прогресс онбординга живёт
// на бэкенде, поэтому пересоздание webview (уход в @BotFather и обратно)
// возвращает ровно на тот шаг, где он остановился.
function entryRouteFor(me) {
  if (!me.cryptobot_connected) return '/onboarding/payment'
  if (!me.bots.length) return '/onboarding/bot'
  if (me.bots.length === 1) return `/shop/${me.bots[0].id}`
  return '/shops'
}

let entryResolved = false

router.beforeEach(async (to) => {
  // витрина покупателя живёт по bot_id из query — онбординг её не касается
  if (getBotId()) return true
  if (entryResolved || to.path !== '/') return true
  entryResolved = true
  try {
    return entryRouteFor(await fetchMe())
  } catch {
    return '/onboarding/payment'
  }
})

export default router
