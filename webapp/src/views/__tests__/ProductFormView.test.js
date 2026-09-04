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

function priceInput(wrapper) {
  return wrapper.findAll('input').find((i) => i.attributes('inputmode') === 'decimal')
}

describe('ProductFormView — цена при редактировании', () => {
  beforeEach(() => {
    vi.clearAllMocks()
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
})
