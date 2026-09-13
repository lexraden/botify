import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const fetchProducts = vi.fn()
const saveProduct = vi.fn()
vi.mock('../../api', () => ({
  fetchProducts: (...a) => fetchProducts(...a),
  saveProduct: (...a) => saveProduct(...a),
  uploadProductImage: vi.fn(),
}))
vi.mock('../../services/telegram', () => ({
  tg: null,
  getBotId: () => 1,
  getInitData: () => '',
  initTelegram: () => {},
  openTelegramLink: () => {},
}))

const router = { push: vi.fn() }
vi.mock('vue-router', () => ({
  useRouter: () => router,
  useRoute: () => ({ params: { botId: '1', id: '7' } }),
}))

const { default: ProductFormView } = await import('../ProductFormView.vue')
const { setLocale } = await import('../../services/locale')

function product(price) {
  return {
    id: 7,
    type: 'physical',
    title: 'Кружка',
    description: null,
    image_url: null,
    price,
    stock: 3,
    is_active: true,
    digital_content: null,
  }
}

async function mountForm(price) {
  fetchProducts.mockResolvedValue([product(price)])
  const wrapper = mount(ProductFormView)
  await flushPromises()
  return wrapper
}

// тип товара выбирается плиткой; ищем по подписи, а не по порядку
function typeButton(wrapper, kind) {
  const labels = { physical: '📦 Товар', digital: '📕 Digital', service: '🛎 Услуга' }
  return wrapper.findAll('.types button').find((b) => b.text() === labels[kind])
}

function priceInput(wrapper) {
  return wrapper.findAll('input').find((i) => i.attributes('inputmode') === 'decimal')
}

describe('ProductFormView — цена при редактировании', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // язык фиксируем: стор локали общий на весь прогон
    setLocale('ru')
  })

  it('целая цена показывается без хвоста нулей', async () => {
    // в базе Numeric(18, 6), наружу приходит «5.000000» — в поле это
    // выглядело как сбой формы
    const wrapper = await mountForm('5.000000')
    expect(priceInput(wrapper).element.value).toBe('5')
  })

  it('дробная цена сохраняет значащие знаки', async () => {
    const wrapper = await mountForm('9.990000')
    expect(priceInput(wrapper).element.value).toBe('9.99')
  })

  it('цена уходит на сохранение неизменной', async () => {
    const wrapper = await mountForm('5.000000')
    saveProduct.mockResolvedValue({})
    await wrapper.find('.actions .btn-primary').trigger('click')
    await flushPromises()
    // botId приходит строкой из параметров маршрута — так его и передаёт форма
    expect(saveProduct).toHaveBeenCalledWith('1', expect.objectContaining({ price: '5' }))
  })

  it('цифровой товар не сохраняется без ссылки выдачи', async () => {
    const w = await mountForm('10')
    await typeButton(w, 'digital').trigger('click')
    await w.find('.btn-primary').trigger('click')
    await flushPromises()

    expect(saveProduct).not.toHaveBeenCalled()
    expect(w.find('.error').text()).toContain('Добавь ссылку')
  })

  it('со ссылкой цифровой товар уходит на сохранение', async () => {
    const w = await mountForm('10')
    await typeButton(w, 'digital').trigger('click')
    await w.find('input[placeholder="https://…"]').setValue('https://example.com/guide')
    await w.find('.btn-primary').trigger('click')
    await flushPromises()

    expect(saveProduct).toHaveBeenCalledTimes(1)
    expect(saveProduct.mock.calls[0][1].digital_content).toEqual({
      url: 'https://example.com/guide',
    })
  })

  it('услуга без ссылки сохраняется: её выполняет человек', async () => {
    const w = await mountForm('10')
    await typeButton(w, 'service').trigger('click')
    await w.find('.btn-primary').trigger('click')
    await flushPromises()

    expect(saveProduct).toHaveBeenCalledTimes(1)
    expect(saveProduct.mock.calls[0][1].digital_content).toBeNull()
  })
})
