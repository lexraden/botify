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
  const tabs = (w) => w.findAll('.vrow button').filter((b) => !b.classes('plus'))
  // поля с inputmode=decimal — цена и старая цена текущего слота
  const nameField = (w) => w.find('.vname input')

  it('по умолчанию вариаций нет — сверху один квадратик V1 и «+»', async () => {
    const w = await mountNew()
    expect(tabs(w).map((b) => b.text())).toEqual(['V1'])
    expect(addBtn(w).exists()).toBe(true)
    // поля названия вариации нет: заполняется обычный товар
    expect(nameField(w).exists()).toBe(false)
    expect(priceInputs(w)).toHaveLength(2) // цена и старая цена
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

  it('«+» добавляет одну вариацию и не теряет уже заполненные поля', async () => {
    const w = await mountNew()
    await priceInputs(w)[0].setValue('12')
    await addBtn(w).trigger('click')

    // добавилась ровно одна — сверху V1 и V2, открыта вторая и она пустая
    expect(tabs(w).map((b) => b.text())).toEqual(['V1', 'V2'])
    expect(tabs(w)[1].classes()).toContain('active')
    expect(priceInputs(w)[0].element.value).toBe('')

    // а введённая до нажатия цена осталась у первой
    await tabs(w)[0].trigger('click')
    expect(priceInputs(w)[0].element.value).toBe('12')
  })

  it('квадратики переключают поля между вариациями', async () => {
    const w = await mountExisting()
    expect(priceInputs(w)[0].element.value).toBe('5') // первая
    await tabs(w)[1].trigger('click')
    expect(priceInputs(w)[0].element.value).toBe('11') // вторая
  })

  it('квадратики подписаны V1, V2 — название вариации в подсказке', async () => {
    const w = await mountExisting()
    expect(tabs(w).map((b) => b.text())).toEqual(['V1', 'V2'])
    expect(tabs(w).map((b) => b.attributes('title'))).toEqual(['Красный', 'Синий'])
    // имя редактируется в той же форме, отдельным полем
    expect(nameField(w).element.value).toBe('Красный')
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
    // у самого товара скидки нет: она своя у каждой вариации
    expect(body.compare_at_price).toBe(null)
    // витринное фото — снимок первой вариации, иначе карточка покажет чужое
    expect(body.image_url).toBe('/api/images/a')
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
    await w.find('.vname .danger').trigger('click')

    expect(tabs(w).map((b) => b.text())).toEqual(['V1'])
    expect(nameField(w).exists()).toBe(false)

    saveProduct.mockResolvedValue({})
    await w.find('.actions .btn-primary').trigger('click')
    await flushPromises()
    expect(saveProduct.mock.calls[0][1].variants).toEqual([])
  })
})

describe('ProductFormView — старая цена у товара без вариаций', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    routeParams = { botId: '1' }
  })

  async function fill(w, price, compare) {
    const inputs = w.findAll('input').filter((i) => i.attributes('inputmode') === 'decimal')
    await w.findAll('input')[0].setValue('Кружка')
    await inputs[0].setValue(price)
    await inputs[1].setValue(compare)
    await w.find('.actions .btn-primary').trigger('click')
    await flushPromises()
  }

  it('уходит на сервер вместе с товаром', async () => {
    const w = mount(ProductFormView)
    await flushPromises()
    saveProduct.mockResolvedValue({})
    await fill(w, '7', '10')

    expect(saveProduct.mock.calls[0][1].compare_at_price).toBe('10')
  })

  it('ниже текущей — не сохраняется', async () => {
    const w = mount(ProductFormView)
    await flushPromises()
    await fill(w, '7', '5')

    expect(saveProduct).not.toHaveBeenCalled()
    expect(w.find('.error').text()).toBeTruthy()
  })

  it('пустая — уходит null, а не пустая строка', async () => {
    const w = mount(ProductFormView)
    await flushPromises()
    saveProduct.mockResolvedValue({})
    await fill(w, '7', '')

    expect(saveProduct.mock.calls[0][1].compare_at_price).toBe(null)
  })
})
