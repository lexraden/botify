import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import ProductCard from '../ProductCard.vue'
import { useCartStore } from '../../stores/cart'
import { setLocale } from '../../services/locale'

const routerStub = { push: () => {} }

function makeCard(product) {
  return mount(ProductCard, {
    props: { product },
    global: { mocks: { $router: routerStub }, stubs: { RouterLink: true } },
  })
}

const plain = { id: 1, title: 'A4 Paper', price: '1.000000', type: 'physical', stock: null }
const withVariants = {
  ...plain,
  id: 2,
  variants: [{ id: 10, price: '1.000000', stock: null, attributes: { '1': 'S' } }],
}

beforeEach(() => {
  localStorage.clear()
  setActivePinia(createPinia())
  setLocale('ru')
})

describe('ProductCard — кнопка добавления и счётчик', () => {
  it('до добавления показывает «Добавить» и не показывает счётчик', () => {
    const wrapper = makeCard(plain)
    expect(wrapper.find('.add').exists()).toBe(true)
    expect(wrapper.find('.stepper').exists()).toBe(false)
  })

  it('товар уже в корзине — только «− +», кнопки «Добавить» под ним нет', async () => {
    const cart = useCartStore()
    cart.add(plain)
    const wrapper = makeCard(plain)
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.stepper').exists()).toBe(true)
    expect(wrapper.find('.badge').text()).toBe('1')
    // ради этого тест и написан: раньше рядом со счётчиком висела «Добавить»
    expect(wrapper.find('.add').exists()).toBe(false)
  })

  it('товар с вариациями набирается тем же «− +», без «Выбрать»', async () => {
    const cart = useCartStore()
    const wrapper = makeCard(withVariants)

    await wrapper.find('.add').trigger('click')
    await wrapper.vm.$nextTick()

    // в корзину легла конкретная вариация: за неё платят и с неё списывают
    const line = Object.values(cart.items)[0]
    expect(line.variant.id).toBe(10)
    expect(wrapper.find('.stepper').exists()).toBe(true)
    expect(wrapper.find('.badge').text()).toBe('1')
    expect(wrapper.text()).not.toContain('Выбрать')
  })

  it('«+» переходит к следующей вариации, когда в первой кончилось', async () => {
    const cart = useCartStore()
    const two = {
      ...withVariants,
      stock: 3,
      variants: [
        { id: 10, price: '1.000000', stock: 1, attributes: { '1': 'S' } },
        { id: 11, price: '1.000000', stock: 2, attributes: { '1': 'M' } },
      ],
    }
    const wrapper = makeCard(two)
    await wrapper.find('.add').trigger('click')
    await wrapper.find('.stepper .plus').trigger('click')
    await wrapper.vm.$nextTick()

    // иначе «+» упирался бы в кончившийся размер при живом остатке товара
    expect(Object.values(cart.items).map((i) => i.variant.id).sort()).toEqual([10, 11])
    expect(wrapper.find('.badge').text()).toBe('2')
  })

  it('«−» снимает штуку, когда набраны разные вариации', async () => {
    const cart = useCartStore()
    const wrapper = makeCard(withVariants)
    await wrapper.find('.add').trigger('click')
    await wrapper.vm.$nextTick()
    await wrapper.find('.stepper .minus').trigger('click')
    await wrapper.vm.$nextTick()

    expect(Object.keys(cart.items)).toHaveLength(0)
    expect(wrapper.find('.stepper').exists()).toBe(false)
  })

  it('без отзывов место справа свободно — показываем зачёркнутую цену', () => {
    const wrapper = makeCard({ ...plain, price: '1.000000', compare_at_price: '2.000000' })
    expect(wrapper.find('.was').text()).toBe('2 USDT')
    expect(wrapper.find('.rating').exists()).toBe(false)
  })

  it('с отзывами место занимает рейтинг — зачёркнутой цены нет', () => {
    const wrapper = makeCard({
      ...plain,
      price: '1.000000',
      compare_at_price: '2.000000',
      reviews_count: 4,
      avg_rating: '4.500000',
    })
    expect(wrapper.find('.rating').exists()).toBe(true)
    expect(wrapper.find('.was').exists()).toBe(false)
  })

  it('у товара с вариациями зачёркнутой цены нет и без отзывов', () => {
    // показанная цена там «от N», собранная из разных вариаций
    const wrapper = makeCard({ ...withVariants, compare_at_price: '9.000000' })
    expect(wrapper.find('.was').exists()).toBe(false)
  })

  it('распроданный товар — неактивная кнопка, без счётчика', () => {
    const wrapper = makeCard({ ...plain, stock: 0 })
    const button = wrapper.find('.add.soldout')
    expect(button.exists()).toBe(true)
    expect(button.attributes('disabled')).toBeDefined()
  })
})
