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

  const addBtn = (w) => w.find('.vrow .plus')
  const pills = (w) => w.findAll('.vrow button').filter((b) => !b.classes('plus'))

  it('по умолчанию вариаций нет — обычная форма и одна кнопка «+»', async () => {
    const w = await mountNew()
    expect(w.find('.variant-card').exists()).toBe(false)
    expect(pills(w)).toHaveLength(0)
    expect(addBtn(w).exists()).toBe(true)
    expect(priceInputs(w)).toHaveLength(1)
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

  it('первое «+» превращает заполненные поля в вариацию 1 и добавляет вторую', async () => {
    const w = await mountNew()
    await priceInputs(w)[0].setValue('12')
    await addBtn(w).trigger('click')

    // две пилюли сверху, поля — у второй
    expect(pills(w)).toHaveLength(2)
    expect(w.find('.variant-card').exists()).toBe(true)
  })

  it('пилюли переключают поля между вариациями', async () => {
    const w = await mountExisting()
    expect(priceInputs(w)[0].element.value).toBe('5') // первая
    await pills(w)[1].trigger('click')
    expect(priceInputs(w)[0].element.value).toBe('11') // вторая
  })

  it('подписи пилюль — из названий вариаций', async () => {
    const w = await mountExisting()
    expect(pills(w).map((b) => b.text())).toEqual(['Красный', 'Синий'])
  })

  it('сохранение шлёт все вариации, цену товара — минимальную', async () => {
    const w = await mountExisting()
    saveProduct.mockResolvedValue({})
    await w.find('.actions .btn-primary').trigger('click')
    await flushPromises()

    const [, body] = saveProduct.mock.calls[0]
    expect(body.variants.map((v) => v.price)).toEqual(['5', '11'])
    expect(body.price).toBe('5')
    // зачёркнутая цена вернулась в форму и уходит на сервер
    expect(body.variants[0].compare_at_price).toBe('9')
  })

  it('старая цена ниже текущей не сохраняется', async () => {
    const w = await mountExisting()
    // поля вариации: цена, старая цена
    await priceInputs(w)[1].setValue('1')
    await w.find('.actions .btn-primary').trigger('click')
    await flushPromises()

    expect(saveProduct).not.toHaveBeenCalled()
    expect(w.find('.error').text()).toBeTruthy()
  })

  it('когда остаётся одна вариация, товар снова становится обычным', async () => {
    const w = await mountExisting()
    await w.find('.variant-head .danger').trigger('click')

    expect(pills(w)).toHaveLength(0)
    expect(w.find('.variant-card').exists()).toBe(false)

    saveProduct.mockResolvedValue({})
    await w.find('.actions .btn-primary').trigger('click')
    await flushPromises()
    expect(saveProduct.mock.calls[0][1].variants).toEqual([])
  })
})
