import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const fetchProducts = vi.fn()
const saveProduct = vi.fn()
const uploadProductImage = vi.fn()
vi.mock('../../api', () => ({
  fetchProducts: (...a) => fetchProducts(...a),
  saveProduct: (...a) => saveProduct(...a),
  uploadProductImage: (...a) => uploadProductImage(...a),
  fetchSubscription: () => Promise.resolve({
    plan: 'free', pro_expires_at: null,
    price_usdt: '20', price_stars: 1500,
    plus_price_usdt: '50', plus_price_stars: 3750,
    period_days: 30, crypto_available: true,
  }),
  createSubscriptionInvoice: vi.fn(),
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
      title: 'Футболка синяя',
      description: 'Тот же крой, другой цвет',
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

  it('название и описание у каждой вариации свои', async () => {
    const w = await mountExisting()
    const titleField = () => w.findAll('input')[0]
    const descField = () => w.find('textarea')

    // у первой своего названия нет — показываем товарное, а не пустое поле
    expect(titleField().element.value).toBe('Футболка')

    await tabs(w)[1].trigger('click')
    expect(titleField().element.value).toBe('Футболка синяя')
    expect(descField().element.value).toBe('Тот же крой, другой цвет')
  })

  it('правка названия на V2 не задевает V1', async () => {
    const w = await mountExisting()
    const titleField = () => w.findAll('input')[0]

    await tabs(w)[1].trigger('click')
    await titleField().setValue('Футболка синяя XL')
    await tabs(w)[0].trigger('click')
    expect(titleField().element.value).toBe('Футболка')

    saveProduct.mockResolvedValue({})
    await w.find('.actions .btn-primary').trigger('click')
    await flushPromises()
    const [, body] = saveProduct.mock.calls[0]
    expect(body.variants.map((v) => v.title)).toEqual(['Футболка', 'Футболка синяя XL'])
    // товарное название — от первой вариации: его читают карточка и заказы
    expect(body.title).toBe('Футболка')
  })

  it('вариация без названия не сохраняется — форма открывает виноватую', async () => {
    const w = await mountExisting()
    await tabs(w)[1].trigger('click')
    await w.findAll('input')[0].setValue('')
    await tabs(w)[0].trigger('click')

    await w.find('.actions .btn-primary').trigger('click')
    await flushPromises()

    expect(saveProduct).not.toHaveBeenCalled()
    expect(w.find('.error').text()).toBeTruthy()
    expect(tabs(w)[1].classes()).toContain('active')
  })

  it('«+» переносит название и описание в новую вариацию', async () => {
    const w = await mountNew()
    await w.findAll('input')[0].setValue('Кружка')
    await w.find('textarea').setValue('Керамика, 300 мл')
    await addBtn(w).trigger('click')

    // расходится обычно цена и фото, а не название — его переносим
    expect(w.findAll('input')[0].element.value).toBe('Кружка')
    expect(w.find('textarea').element.value).toBe('Керамика, 300 мл')
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

  it('предупреждение уходит, как только поле поправили', async () => {
    const w = await mountExisting()
    await priceInputs(w)[1].setValue('1') // старая цена ниже текущей
    await w.find('.actions .btn-primary').trigger('click')
    await flushPromises()
    expect(w.find('.error').exists()).toBe(true)

    // раньше сообщение висело над уже верным полем до следующего «Сохранить»
    await priceInputs(w)[1].setValue('20')
    await flushPromises()
    expect(w.find('.error').exists()).toBe(false)
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

describe('ProductFormView — действия над фото', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    routeParams = { botId: '1', id: '7' }
  })

  const WITH_PHOTO = {
    id: 7,
    type: 'physical',
    title: 'Футболка',
    description: null,
    image_url: '/api/images/a',
    price: '12.000000',
    stock: 5,
    is_active: true,
    digital_content: null,
    variants: [],
  }

  async function mountWithPhoto() {
    fetchProducts.mockResolvedValue([WITH_PHOTO])
    const w = mount(ProductFormView)
    await flushPromises()
    return w
  }

  it('свёрнуто — только значок, кнопок в разметке нет', async () => {
    const w = await mountWithPhoto()
    expect(w.find('.edit-hint').exists()).toBe(true)
    expect(w.find('.photo-actions').exists()).toBe(false)
  })

  it('по нажатию на фото поверх него появляются «Заменить» и «Удалить»', async () => {
    const w = await mountWithPhoto()
    await w.find('.thumb.big').trigger('click')

    const actions = w.find('.photo-actions')
    expect(actions.exists()).toBe(true)
    expect(actions.findAll('button').map((b) => b.text())).toEqual(['Replace', 'Remove'])
    // значок уступает место кнопкам, а не наслаивается на них
    expect(w.find('.edit-hint').exists()).toBe(false)
  })

  it('кнопки лежат внутри самого фото, а не рядом с ним', async () => {
    // ради этого тест и написан: .image-box была flex-строкой, thumb забирал
    // всю ширину, и кнопки уезжали за правый край экрана
    const w = await mountWithPhoto()
    await w.find('.thumb.big').trigger('click')
    expect(w.find('.thumb.big .photo-actions').exists()).toBe(true)
  })

  it('«Удалить» возвращает зону загрузки', async () => {
    const w = await mountWithPhoto()
    await w.find('.thumb.big').trigger('click')
    await w.find('.photo-actions .danger').trigger('click')

    expect(w.find('.thumb.big').exists()).toBe(false)
    expect(w.find('.drop-zone').exists()).toBe(true)
  })
})

describe('ProductFormView — упёрлись в лимит тарифа', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    routeParams = { botId: '1' }
  })

  it('403 про лимит открывает тарифы, а не красную строку', async () => {
    const w = mount(ProductFormView)
    await flushPromises()
    await w.findAll('input')[0].setValue('Одиннадцатый товар')
    await w.findAll('input').filter((i) => i.attributes('inputmode') === 'decimal')[0].setValue('5')

    saveProduct.mockRejectedValue({
      response: { status: 403, data: { detail: 'plan limit reached: 10 товаров на бесплатном тарифе' } },
    })
    await w.find('.actions .btn-primary').trigger('click')
    await flushPromises()

    // внутренняя строка бэкенда покупателю ничего не объясняет — вместо неё окно
    expect(w.find('.error').exists()).toBe(false)
    expect(w.find('.tier').exists()).toBe(true)
  })

  it('обычная ошибка сохранения по-прежнему строкой', async () => {
    const w = mount(ProductFormView)
    await flushPromises()
    await w.findAll('input')[0].setValue('Товар')
    await w.findAll('input').filter((i) => i.attributes('inputmode') === 'decimal')[0].setValue('5')

    saveProduct.mockRejectedValue({ response: { status: 500, data: {} } })
    await w.find('.actions .btn-primary').trigger('click')
    await flushPromises()

    expect(w.find('.tier').exists()).toBe(false)
    expect(w.find('.error').exists()).toBe(true)
  })
})
