import { t } from '../i18n'

// Коды, которые бэкенд возвращает в detail осознанно, — у каждого свой текст.
// Всё остальное (`insufficient stock for «Кружка»: 2 left`, `foreign order`,
// массив ошибок валидации от Pydantic) наружу не показывается: это внутренние
// строки, покупателю они ничего не объясняют и написаны по-английски.
const CODES = {
  delivery_required: 'checkout.deliveryRequired',
  chat_locked: 'chat.errLocked',
  too_many_messages: 'chat.errRate',
  banned: 'errors.banned',
  'shop not found': 'errors.shopClosed',
  'foreign order': 'errors.foreignOrder',
  invoice_failed: 'errors.invoiceFailed',
}

/** Человеческий текст ошибки запроса. fallbackKey — ключ i18n по умолчанию. */
export function apiError(e, fallbackKey) {
  const status = e?.response?.status
  const detail = e?.response?.data?.detail

  if (typeof detail === 'string' && CODES[detail]) return t(CODES[detail])

  // Заказ уже оплатили/отменили в другой вкладке, пока экран висел открытым
  if (status === 409) return t('errors.orderChanged')
  if (status === 413) return t('errors.tooBig')
  return t(fallbackKey)
}
