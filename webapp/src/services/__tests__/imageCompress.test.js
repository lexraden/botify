import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { compressImage } from '../imageCompress'

// jsdom не умеет ни декодировать картинки, ни toBlob — подменяем оба конца
// пути и проверяем поведение, а не работу браузерного кодека.
function stubCanvas(blobFactory) {
  const ctx = { drawImage: vi.fn() }
  vi.spyOn(document, 'createElement').mockImplementation((tag) => {
    if (tag !== 'canvas') return document.createElementNS('http://www.w3.org/1999/xhtml', tag)
    return {
      width: 0,
      height: 0,
      getContext: () => ctx,
      toBlob: (cb, type, quality) => cb(blobFactory(type, quality)),
    }
  })
  return ctx
}

function file(bytes, type = 'image/jpeg', name = 'photo.jpg') {
  return new File([new Uint8Array(bytes)], name, { type })
}

describe('compressImage', () => {
  beforeEach(() => {
    globalThis.createImageBitmap = vi.fn(async () => ({ width: 4000, height: 3000, close: vi.fn() }))
  })

  afterEach(() => {
    vi.restoreAllMocks()
    delete globalThis.createImageBitmap
  })

  it('ужимает длинную сторону до 1600 и отдаёт webp', async () => {
    const ctx = stubCanvas((type) => new Blob([new Uint8Array(1000)], { type }))
    const out = await compressImage(file(500000))

    expect(out.type).toBe('image/webp')
    expect(out.name).toBe('photo.webp')
    expect(out.size).toBeLessThan(500000)
    // 4000x3000 -> 1600x1200: пропорции сохранены
    const [, , , w, h] = ctx.drawImage.mock.calls[0]
    expect([w, h]).toEqual([1600, 1200])
  })

  it('учитывает EXIF-поворот при декодировании', async () => {
    stubCanvas((type) => new Blob([new Uint8Array(10)], { type }))
    await compressImage(file(500000))
    expect(globalThis.createImageBitmap).toHaveBeenCalledWith(
      expect.anything(),
      { imageOrientation: 'from-image' },
    )
  })

  it('GIF не трогает: canvas оставил бы один кадр вместо анимации', async () => {
    stubCanvas((type) => new Blob([new Uint8Array(10)], { type }))
    const gif = file(900000, 'image/gif', 'loop.gif')
    expect(await compressImage(gif)).toBe(gif)
  })

  it('если сжатое тяжелее оригинала — отправляем оригинал', async () => {
    stubCanvas((type) => new Blob([new Uint8Array(9000)], { type }))
    const small = file(1000, 'image/png', 'icon.png')
    expect(await compressImage(small)).toBe(small)
  })

  it('зависший кодек не подвешивает загрузку: по таймауту идёт оригинал', async () => {
    // createImageBitmap падает, путь уходит на <img>, а тот не отвечает ни
    // onload, ни onerror — без страховки промис не завершался бы никогда
    vi.useFakeTimers()
    globalThis.createImageBitmap = vi.fn(async () => {
      throw new Error('decode failed')
    })
    const original = file(500000)
    const pending = compressImage(original)
    await vi.advanceTimersByTimeAsync(11_000)
    expect(await pending).toBe(original)
    vi.useRealTimers()
  })

  it('не картинку не трогает', async () => {
    const pdf = file(100, 'application/pdf', 'doc.pdf')
    expect(await compressImage(pdf)).toBe(pdf)
  })
})
