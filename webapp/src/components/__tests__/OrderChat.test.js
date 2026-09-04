import { describe, expect, it, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

vi.mock('../../api', () => ({
  fetchOrderChat: vi.fn(),
  sendOrderChatMessage: vi.fn(),
  sendOrderChatPhoto: vi.fn(),
}))

import OrderChat from '../OrderChat.vue'
import { fetchOrderChat, sendOrderChatMessage, sendOrderChatPhoto } from '../../api'
import { setLocale } from '../../services/locale'

const openChat = {
  status: 'active',
  can_send: true,
  closes_at: null,
  messages: [
    { id: 1, sender: 'seller', body: 'Заказ собран', created_at: '2026-08-24T10:00:00Z' },
    { id: 2, sender: 'customer', body: 'Спасибо!', created_at: '2026-08-24T10:01:00Z' },
  ],
}

beforeEach(() => {
  vi.clearAllMocks()
  // в happy-dom navigator.language = en-US, а тесты про русский UI
  setLocale('ru')
})

describe('OrderChat — чат заказа', () => {
  it('рисует пузыри обеих сторон с ролями отправителей', async () => {
    fetchOrderChat.mockResolvedValue(openChat)
    const wrapper = mount(OrderChat, { props: { botId: 1, orderId: 10 } })
    await flushPromises()

    const seller = wrapper.find('.msg.seller')
    const customer = wrapper.find('.msg.customer')
    expect(seller.exists()).toBe(true)
    expect(seller.text()).toContain('Заказ собран')
    expect(customer.text()).toContain('Спасибо!')
    // личность собеседника не раскрывается нигде
    expect(wrapper.text()).not.toContain('@')
  })

  it('при закрытом окне инпут скрыт и показана плашка', async () => {
    fetchOrderChat.mockResolvedValue({ ...openChat, can_send: false })
    const wrapper = mount(OrderChat, { props: { botId: 1, orderId: 10 } })
    await flushPromises()

    expect(wrapper.find('.composer').exists()).toBe(false)
    expect(wrapper.find('.locked').text()).toContain(
      'Этот чат закрыт для новых сообщений',
    )
  })

  it('кнопка отправки подсвечена и при пустом поле: клик просто ничего не шлёт', async () => {
    fetchOrderChat.mockResolvedValue(openChat)
    const wrapper = mount(OrderChat, { props: { botId: 1, orderId: 10 } })
    await flushPromises()

    const send = wrapper.find('.send')
    expect(send.attributes('disabled')).toBeUndefined()
    await send.trigger('click')
    await flushPromises()
    expect(sendOrderChatMessage).not.toHaveBeenCalled()
  })

  it('отправка уходит в API и перечитывает историю', async () => {
    fetchOrderChat
      .mockResolvedValueOnce(openChat)
      .mockResolvedValueOnce({
        ...openChat,
        messages: [...openChat.messages, { id: 3, sender: 'seller', body: 'Уже едет', created_at: '2026-08-24T10:02:00Z' }],
      })
    sendOrderChatMessage.mockResolvedValue({ id: 3, sender: 'seller', body: 'Уже едет' })

    const wrapper = mount(OrderChat, { props: { botId: 1, orderId: 10 } })
    await flushPromises()

    await wrapper.find(".composer input[placeholder='Сообщение…']").setValue('Уже едет')
    await wrapper.find('.send').trigger('click')
    await flushPromises()

    expect(sendOrderChatMessage).toHaveBeenCalledWith(1, 10, 'Уже едет')
    expect(fetchOrderChat).toHaveBeenCalledTimes(2)
    expect(wrapper.find(".composer input[placeholder='Сообщение…']").element.value).toBe('')
  })

  it('кнопка «+» отправляет файл сразу, черновик уезжает подписью', async () => {
    fetchOrderChat.mockResolvedValue(openChat)
    sendOrderChatPhoto.mockResolvedValue({
      id: 3,
      sender: 'seller',
      body: 'вот фото',
      image_url: '/api/chat-images/tok',
    })

    const wrapper = mount(OrderChat, { props: { botId: 1, orderId: 10 } })
    await flushPromises()

    await wrapper.find(".composer input[placeholder='Сообщение…']").setValue('вот фото')
    const file = new File([new Uint8Array([1, 2, 3])], 'photo.jpg', { type: 'image/jpeg' })
    Object.defineProperty(wrapper.find('input[type=file]').element, 'files', { value: [file] })
    await wrapper.find('input[type=file]').trigger('change')
    await flushPromises()

    expect(sendOrderChatPhoto).toHaveBeenCalledWith(1, 10, file, 'вот фото')
    expect(fetchOrderChat).toHaveBeenCalledTimes(2)
    expect(wrapper.find(".composer input[placeholder='Сообщение…']").element.value).toBe('')
  })

  it('ошибка загрузки фото показывается по коду ответа', async () => {
    fetchOrderChat.mockResolvedValue(openChat)
    sendOrderChatPhoto.mockRejectedValue({ response: { status: 413 } })

    const wrapper = mount(OrderChat, { props: { botId: 1, orderId: 10 } })
    await flushPromises()

    const file = new File([new Uint8Array([1])], 'big.jpg', { type: 'image/jpeg' })
    Object.defineProperty(wrapper.find('input[type=file]').element, 'files', { value: [file] })
    await wrapper.find('input[type=file]').trigger('change')
    await flushPromises()

    expect(wrapper.find('.error').text()).toBe('Фото больше 5 МБ — выбери поменьше.')
  })

  it('сообщение с фото рисует картинку со ссылкой на полный размер', async () => {
    fetchOrderChat.mockResolvedValue({
      ...openChat,
      messages: [
        ...openChat.messages,
        {
          id: 3,
          sender: 'customer',
          body: 'смотрите',
          image_url: '/api/chat-images/abc123',
          created_at: '2026-08-24T10:02:00Z',
        },
      ],
    })
    const wrapper = mount(OrderChat, { props: { botId: 1, orderId: 10 } })
    await flushPromises()

    const photoMsg = wrapper.findAll('.msg.customer').at(-1)
    const img = photoMsg.find('.photo')
    expect(img.exists()).toBe(true)
    expect(img.attributes('src')).toBe('/api/chat-images/abc123')
    expect(photoMsg.find('.bubble a').attributes('href')).toBe(
      '/api/chat-images/abc123',
    )
    expect(photoMsg.find('.bubble').text()).toContain('смотрите')
  })
})
