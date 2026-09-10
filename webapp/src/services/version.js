// Версия Mini App: пробрасывается в сборку через define в vite.config.js
// (читается из package.json). typeof-гвард нужен для vitest — там define нет,
// и глобальная константа просто не определена. Уезжает в фидбек («Связаться
// с нами»), чтобы по обращению было видно, на какой сборке человек сидел.
export const APP_VERSION = typeof __APP_VERSION__ === 'undefined' ? '' : __APP_VERSION__
