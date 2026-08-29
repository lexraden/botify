import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const fetchProducts = vi.fn()
const saveProduct = vi.fn()
const uploadProductImage = vi.fn()
vi.mock('../../api', () => ({
  fetchProducts: (...a) => fetchProducts(...a),
  saveProduct: (...a) => saveProduct(...a),
  uploadProductImage: (...a) => uploadProductImage(...a),
}))
vi.mock('../../services/telegram', () => ({
  tg: null,
  getBotId: () => 1,
  getInitData: () => '',
  initTelegram: () => {},
  openTelegramLink: () => {},
}))

const router = { push: vi.fn() }
let routeParams = { botId: '1' }
vi.mock('vue-router', () => ({
  useRouter: () => router,
  useRoute: () => ({ params: routeParams }),
}))

const { default: ProductFormView } = await import('../ProductFormView.vue')

const SAVED = {
  id: 7,
  type: 'physical',
  title: 'Футболка',
  description: null,
  image_url: null,
  price: '5.000000',
  stock: 5,
  is_active: true,
  digital_content: null,
  variants: [
    {
      id: 10,
      sku: 'TSH-R',
      attributes: { Цвет: 'Красный' },
      price: '5.000000',
      compare_at_price: '9.000000',
      stock: 3,
      images: ['/api/images/a'],
      is_active: true,
    },
    {
      id: 11,
      sku: null,
      attributes: { Цвет: 'Синий' },
      price: '11.000000',
      compare_at_price: null,
      stock: 2,
      images: null,
      is_active: true,
    },
  ],
}

function priceInputs(w) {
  return w.findAll('input').filter((i) => i.attributes('inputmode') === 'decimal')
}

describe('ProductFormView — вариации', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    routeParams = { botId: '1' }
  })

  async function mountNew() {
    const w = mount(ProductFormView)
    await flushPromises()
    return w
  }

  async function mountExisting() {
    routeParams = { botId: '1', id: '7' }
    fetchProducts.mockResolvedValue([SAVED])
    const w = mount(ProductFormView)
    await flushPromises()
    return w
  }

  it('по умолчанию вариаций нет — обычная форма', async () => {
    const w = await mountNew()
    expect(w.find('.variant-card').exists()).toBe(false)
    // цена одна, поле названия вариации не показано
    expect(priceInputs(w)).toHaveLength(1)
    expect(w.find('.add-variant').exists()).toBe(true)
  })

  it('товар без вариаций сохраняется без них — в базе не заводится ни строки', async () => {
    const w = await mountNew()
    saveProduct.mockResolvedValue({})
    await w.findAll('input')[0].setValue('Кружка')
    await priceInputs(w)[0].setValue('7')
    await w.find('.actions .btn-primary').trigger('click')
    await flushPromises()

    const [, body] = saveProduct.mock.calls[0]
    expect(body.variants).toEqual([])
    expect(body.price).toBe('7')
  })

  it('«+» открывает такой же блок ниже, ничего не требуя заранее', async () => {
    const w = await mountNew()
    await priceInputs(w)[0].setValue('12')
    await w.find('.add-variant').trigger('click')

    expect(w.findAll('.variant-card')).toHaveLength(1)
    // блок наследует цену товара — правит продавец только отличия
    expect(priceInputs(w)[1].element.value).toBe('12')
  })

  it('базовые поля становятся первой вариацией, добавленный блок — второй', async () => {
    const w = await mountNew()
    saveProduct.mockResolvedValue({})
    await w.findAll('input')[0].setValue('Футболка')
    await priceInputs(w)[0].setValue('5')
    await w.find('.add-variant').trigger('click')
    await priceInputs(w)[1].setValue('11')
    await w.find('.actions .btn-primary').trigger('click')
    await flushPromises()

    const [, body] = saveProduct.mock.calls[0]
    expect(body.variants).toHaveLength(2)
    expect(body.variants.map((v) => v.price)).toEqual(['5', '11'])
    // витринная цена товара — минимальная из вариаций
    expect(body.price).toBe('5')
  })

  it('название вариации уходит свойством', async () => {
    const w = await mountNew()
    saveProduct.mockResolvedValue({})
    await w.findAll('input')[0].setValue('Футболка')
    await priceInputs(w)[0].setValue('5')
    await w.find('.add-variant').trigger('click')
    // первое текстовое поле блока — название вариации
    const labels = w.findAll('.variant-card input')
    await labels[0].setValue('Синий, L')
    await w.find('.actions .btn-primary').trigger('click')
    await flushPromises()

    const [, body] = saveProduct.mock.calls[0]
    expect(Object.values(body.variants[1].attributes)).toEqual(['Синий, L'])
  })

  it('сохранённый товар раскладывается обратно: первая в форму, остальные блоками', async () => {
    const w = await mountExisting()
    // базовая цена — от первой вариации
    expect(priceInputs(w)[0].element.value).toBe('5')
    // вторая пришла отдельным блоком
    expect(w.findAll('.variant-card')).toHaveLength(1)
    expect(priceInputs(w)[1].element.value).toBe('11')
  })

  it('убрать блок можно, и тогда остаётся обычный товар', async () => {
    const w = await mountExisting()
    await w.find('.variant-head .danger').trigger('click')
    expect(w.findAll('.variant-card')).toHaveLength(0)

    saveProduct.mockResolvedValue({})
    await w.find('.actions .btn-primary').trigger('click')
    await flushPromises()
    expect(saveProduct.mock.calls[0][1].variants).toEqual([])
  })
})
