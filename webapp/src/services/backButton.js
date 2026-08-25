// Системная кнопка «Назад» Telegram на внутренних экранах.
// Без неё жест назад на Android сворачивает весь Mini App — покупатель
// одним случайным движением теряет магазин. Корень ('/') живёт без кнопки:
// из каталога назад и уходить некуда.
import { tg } from './telegram'

// Куда ведёт «Назад» с текущего экрана. 'BACK' — шаг истории внутри приложения,
// '/' — принудительно в каталог. Из «Моих покупок» историю не шагаем: после
// оплаты предыдущий экран — пустая корзина, туда возвращать нечего.
export function backTarget(path, hasInAppHistory) {
  if (path === '/my-orders') return '/'
  return hasInAppHistory ? 'BACK' : '/'
}

// Вешается один раз при старте приложения (main.js)
export function attachBackButton(router) {
  const bb = tg?.BackButton
  if (!bb) return

  let currentPath = '/'

  bb.onClick(() => {
    const target = backTarget(currentPath, window.history.state?.back != null)
    // промис возвращаем для тестов; Telegram его игнорирует
    return target === 'BACK' ? router.back() : router.push(target)
  })

  router.afterEach((to) => {
    currentPath = to.path
    if (to.path === '/') bb.hide()
    else bb.show()
  })
}
