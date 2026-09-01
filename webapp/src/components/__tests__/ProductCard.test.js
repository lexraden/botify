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

  it('у товара с вариациями остаётся «Выбрать», даже когда он уже в корзине', async () => {
    const cart = useCartStore()
    cart.add(withVariants, withVariants.variants[0])
    const wrapper = makeCard(withVariants)
    await wrapper.vm.$nextTick()

    // выбор размера живёт на странице товара, а не в сетке — «− +» тут врали бы
    expect(wrapper.find('.stepper').exists()).toBe(false)
    expect(wrapper.find('.add').text()).toBe('Выбрать')
    expect(wrapper.find('.badge').text()).toBe('1')
  })

  it('в сетке одна цена: зачёркнутая живёт на странице товара', () => {
    const wrapper = makeCard({ ...plain, price: '1.000000', compare_at_price: '2.000000' })
    expect(wrapper.find('.was').exists()).toBe(false)
    expect(wrapper.find('.price').text()).toContain('1 USDT')
    // и старое число не просочилось в карточку никаким другим способом
    expect(wrapper.find('.price').text()).not.toContain('2')
  })

  it('распроданный товар — неактивная кнопка, без счётчика', () => {
    const wrapper = makeCard({ ...plain, stock: 0 })
    const button = wrapper.find('.add.soldout')
    expect(button.exists()).toBe(true)
    expect(button.attributes('disabled')).toBeDefined()
  })
})
