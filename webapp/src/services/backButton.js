// Системная кнопка «Назад» Telegram на внутренних экранах.
// Без неё жест назад на Android сворачивает весь Mini App — покупатель
// одним случайным движением теряет магазин. Корень ('/') живёт без кнопки:
// из каталога назад и уходить некуда.
import { tg } from './telegram'

// Куда ведёт «Назад» с текущего экрана. backPath — предыдущий экран внутренней
// истории (window.history.state.back), null — истории нет. 'BACK' — шаг назад,
// '/' — принудительно в каталог. Исключение: «Мои покупки», открытые сразу
// после оплаты, — шагом истории туда попадает пустая корзина, возвращаем в каталог.
export function backTarget(path, backPath) {
  if (path === '/my-orders' && backPath === '/checkout') return '/'
  return backPath ? 'BACK' : '/'
}

// Листы поверх экрана (например, окно тарифов) забирают «Назад» себе: пока
// лист открыт, назад обязан закрывать его, а не уводить с экрана под ним.
// Стек, а не одна ссылка: лист может открыться поверх листа, и закрываться
// они должны в обратном порядке.
const interceptors = []

export function pushBackInterceptor(fn) {
  interceptors.push(fn)
}

export function popBackInterceptor(fn) {
  const i = interceptors.lastIndexOf(fn)
  if (i !== -1) interceptors.splice(i, 1)
}

// Вешается один раз при старте приложения (main.js)
export function attachBackButton(router) {
  const bb = tg?.BackButton
  if (!bb) return

  let currentPath = '/'

  bb.onClick(() => {
    const top = interceptors[interceptors.length - 1]
    if (top) {
      top()
      return
    }
    const target = backTarget(currentPath, window.history.state?.back ?? null)
    // промис возвращаем для тестов; Telegram его игнорирует
    return target === 'BACK' ? router.back() : router.push(target)
  })

  router.afterEach((to) => {
    currentPath = to.path
    if (to.path === '/') bb.hide()
    else bb.show()
  })
}
