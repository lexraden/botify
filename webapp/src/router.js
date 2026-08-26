import { createRouter, createWebHistory } from 'vue-router'
import { getBotId } from './services/telegram'
import { fetchMe } from './api'

import StoreView from './views/StoreView.vue'
import ProductDetailView from './views/ProductDetailView.vue'
import CheckoutView from './views/CheckoutView.vue'
import ProfileView from './views/ProfileView.vue'
import MyOrdersView from './views/MyOrdersView.vue'
import WelcomeView from './views/WelcomeView.vue'
import OnboardingBot from './views/OnboardingBot.vue'
import OnboardingDone from './views/OnboardingDone.vue'
import ShopsView from './views/ShopsView.vue'
import ShopView from './views/ShopView.vue'
import ProductFormView from './views/ProductFormView.vue'
import OrderChatView from './views/OrderChatView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    // покупатель — Mini App открыт из seller-бота (есть ?bot_id=)
    { path: '/', name: 'store', component: StoreView },
    { path: '/product/:id', name: 'product', component: ProductDetailView },
    { path: '/checkout', component: CheckoutView },
    { path: '/profile', name: 'profile', component: ProfileView },
    { path: '/my-orders', name: 'my-orders', component: MyOrdersView },
    // продавец — Mini App открыт из hub-бота
    { path: '/onboarding/welcome', component: WelcomeView },
    { path: '/onboarding/bot', component: OnboardingBot },
    { path: '/onboarding/done', component: OnboardingDone },
    { path: '/shops', component: ShopsView },
    { path: '/shop/:botId', component: ShopView },
    { path: '/shop/:botId/product/:id?', component: ProductFormView },
    { path: '/shop/:botId/orders/:orderId/chat', component: OrderChatView },
  ],
})

// Куда отправить продавца при открытии приложения. Прогресс онбординга живёт
// на бэкенде, поэтому пересоздание webview (уход в @BotFather и обратно)
// возвращает ровно на тот шаг, где он остановился.
function entryRouteFor(me) {
  if (!me.bots.length) {
    // онбординг не завершён: сперва условия, затем единственный шаг — бот
    if (!me.terms_accepted) return '/onboarding/welcome'
    return '/onboarding/bot'
  }
  // один активный бот — сразу в магазин; отключён или их несколько — в список:
  // там видно статусы всех ботов и есть «Добавить магазин»
  if (me.bots.length === 1 && me.bots[0].is_active) return `/shop/${me.bots[0].id}`
  return '/shops'
}

// «Reload Page» в Telegram перезагружает текущий адрес, а bot_id в нём живёт
// только пока его кто-то переносит: цели переходов пишутся чистым path.
// Прокидываем параметр в каждый переход, где его нет, — тогда адрес всегда
// остаётся с bot_id и перезагрузка витрины не уводит покупателя в онбординг.
router.beforeEach((to, from) => {
  const botId = to.query.bot_id ?? from.query.bot_id ?? getBotId()
  if (!botId || to.query.bot_id === botId) return true
  return { path: to.path, query: { ...to.query, bot_id: botId }, hash: to.hash }
})

let entryResolved = false

router.beforeEach(async (to) => {
  // витрина покупателя живёт по bot_id из query — онбординг её не касается
  if (getBotId()) return true
  if (entryResolved || to.path !== '/') return true
  entryResolved = true
  try {
    return entryRouteFor(await fetchMe())
  } catch {
    return '/onboarding/welcome'
  }
})

export default router
