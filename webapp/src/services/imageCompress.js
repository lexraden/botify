// Сжатие фото перед отправкой.
//
// Снимок с телефона — это 3-5 МБ, и до сих пор он ложился в Postgres как есть.
// Витрина с десятком товаров тянула десятки мегабайт на мобильном интернете,
// база росла быстрее всего остального, а бэкапы — пропорционально. После
// сжатия то же фото весит 150-300 КБ, и на экране телефона разницы не видно.
//
// Делается на клиенте намеренно: сжатие на сервере потребовало бы Pillow,
// процессорной работы в том же процессе, который обслуживает вебхуки платежей,
// и лишнего риска на денежном пути.
//
// Правило простое: не смогли сжать — отправляем оригинал. Сжатие это
// оптимизация, а не условие загрузки, и оно не должно мешать продавцу
// выложить товар.

// Потолок на выбранный файл. Это не серверный лимит (5 МБ на то, что реально
// уедет), а защита от заведомо неподъёмного файла: снимок с телефона в него
// укладывается с большим запасом, а после сжатия уходит 150-300 КБ.
export const MAX_PICK_MB = 25

export const MAX_SIDE = 1600
export const WEBP_QUALITY = 0.82
export const JPEG_QUALITY = 0.85

// Сжатие не должно уметь подвесить загрузку. Декодирование идёт через
// браузерный кодек, и если он ни разу не ответит (битый файл, экзотический
// формат), промис не завершится вовсе — у продавца навсегда останется
// «Загрузка…» и заблокированная кнопка. По истечении срока просто отправляем
// оригинал.
const TIMEOUT_MS = 10_000

// Анимацию canvas не сохраняет — из GIF получился бы один кадр. Пропускаем
// такие файлы нетронутыми: лучше тяжёлый живой GIF, чем лёгкая картинка,
// которая внезапно перестала двигаться.
const PASS_THROUGH = new Set(['image/gif'])

async function decode(file) {
  // createImageBitmap с imageOrientation учитывает EXIF-поворот: без него
  // вертикальные фото с телефона уезжают набок.
  if (typeof createImageBitmap === 'function') {
    try {
      return await createImageBitmap(file, { imageOrientation: 'from-image' })
    } catch {
      /* старый браузер не знает опцию — пробуем через <img> */
    }
  }
  const url = URL.createObjectURL(file)
  try {
    return await new Promise((resolve, reject) => {
      const img = new Image()
      img.onload = () => resolve(img)
      img.onerror = () => reject(new Error('decode failed'))
      img.src = url
    })
  } finally {
    URL.revokeObjectURL(url)
  }
}

function toBlob(canvas, type, quality) {
  return new Promise((resolve) => canvas.toBlob(resolve, type, quality))
}

/**
 * Уменьшает и пережимает картинку. Возвращает File — исходный либо сжатый.
 * Никогда не бросает: любая осечка означает «отправляем как есть».
 */
export async function compressImage(file, { maxSide = MAX_SIDE } = {}) {
  if (!file || !file.type?.startsWith('image/') || PASS_THROUGH.has(file.type)) return file

  let timer
  const deadline = new Promise((resolve) => {
    timer = setTimeout(() => resolve(file), TIMEOUT_MS)
  })
  try {
    return await Promise.race([shrink(file, maxSide), deadline])
  } catch {
    return file
  } finally {
    clearTimeout(timer)
  }
}

async function shrink(file, maxSide) {
  try {
    const bitmap = await decode(file)
    const width = bitmap.width || bitmap.naturalWidth
    const height = bitmap.height || bitmap.naturalHeight
    if (!width || !height) return file

    const scale = Math.min(1, maxSide / Math.max(width, height))
    const canvas = document.createElement('canvas')
    canvas.width = Math.round(width * scale)
    canvas.height = Math.round(height * scale)
    const ctx = canvas.getContext('2d')
    if (!ctx) return file
    ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
    bitmap.close?.()

    // WebP жмёт заметно лучше; где его нет (старые Safari) — JPEG
    let blob = await toBlob(canvas, 'image/webp', WEBP_QUALITY)
    let type = 'image/webp'
    if (!blob || blob.type !== 'image/webp') {
      blob = await toBlob(canvas, 'image/jpeg', JPEG_QUALITY)
      type = 'image/jpeg'
    }
    // Мелкая картинка после пережатия может стать тяжелее — тогда оригинал
    if (!blob || blob.size >= file.size) return file

    const name = file.name?.replace(/\.[^.]+$/, '') || 'photo'
    const ext = type === 'image/webp' ? 'webp' : 'jpg'
    return new File([blob], `${name}.${ext}`, { type })
  } catch {
    return file
  }
}
