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

  it('без вариаций форма показывает цену и остаток самого товара', async () => {
    const w = await mountNew()
    expect(w.find('.variant-card').exists()).toBe(false)
    expect(priceInputs(w).length).toBe(1)
  })

  it('«+» заводит вариацию и наследует базовые данные товара', async () => {
    const w = await mountNew()
    await priceInputs(w)[0].setValue('12')
    await w.find('.variant-tabs .add').trigger('click')

    const card = w.find('.variant-card')
    expect(card.exists()).toBe(true)
    // цена вариации предзаполнена ценой товара
    expect(priceInputs(w)[0].element.value).toBe('12')
  })

  it('вкладки переключают поля на выбранную вариацию', async () => {
    const w = await mountExisting()
    // открыта первая: её цена 5
    expect(priceInputs(w)[0].element.value).toBe('5')

    const tabs = w.findAll('.variant-tabs .tab')
    await tabs[1].trigger('click') // вторая вариация
    expect(priceInputs(w)[0].element.value).toBe('11')
  })

  it('подписи вкладок собираются из свойств вариации', async () => {
    const w = await mountExisting()
    const labels = w.findAll('.variant-tabs .tab .label').map((n) => n.text())
    expect(labels.slice(0, 2)).toEqual(['Красный', 'Синий'])
  })

  it('сохранение шлёт вариации, а цену товара — минимальную из них', async () => {
    const w = await mountExisting()
    saveProduct.mockResolvedValue({})
    await w.find('.actions .btn-primary').trigger('click')
    await flushPromises()

    const [, body] = saveProduct.mock.calls[0]
    expect(body.variants).toHaveLength(2)
    expect(body.variants[0]).toMatchObject({
      id: 10,
      price: '5',
      compare_at_price: '9',
      stock: 3,
      attributes: { Цвет: 'Красный' },
      images: ['/api/images/a'],
    })
    // витринная цена товара — минимальная по вариациям
    expect(body.price).toBe('5')
  })

  it('старая цена ниже текущей не сохраняется', async () => {
    const w = await mountExisting()
    // у первой вариации ставим старую цену ниже текущей
    const inputs = priceInputs(w)
    await inputs[1].setValue('1') // compare_at_price
    await w.find('.actions .btn-primary').trigger('click')
    await flushPromises()

    expect(saveProduct).not.toHaveBeenCalled()
    expect(w.find('.error').text()).toBeTruthy()
  })

  it('удаление вариации убирает вкладку', async () => {
    const w = await mountExisting()
    await w.find('.variant-head .danger').trigger('click')
    // осталась одна вариация плюс кнопка «добавить»
    expect(w.findAll('.variant-tabs .tab')).toHaveLength(2)
  })
})
