import { describe, expect, it, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

vi.mock('../../api', () => ({
  fetchOrderChat: vi.fn(),
  sendOrderChatMessage: vi.fn(),
}))

import OrderChat from '../OrderChat.vue'
import { fetchOrderChat, sendOrderChatMessage } from '../../api'

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

    await wrapper.find('.composer input').setValue('Уже едет')
    await wrapper.find('.send').trigger('click')
    await flushPromises()

    expect(sendOrderChatMessage).toHaveBeenCalledWith(1, 10, 'Уже едет')
    expect(fetchOrderChat).toHaveBeenCalledTimes(2)
    expect(wrapper.find('.composer input').element.value).toBe('')
  })
})
