import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import LoadingOverlay from '../LoadingOverlay.vue'
import { startLoading, stopLoading } from '../../services/loading'

// оверлей показывается с задержкой SHOW_AFTER_MS (150 мс), исчезает после
// fade-перехода — в обоих случаях ждём с запасом
const SETTLE_MS = 300

describe('LoadingOverlay', () => {
  it('показывает подпись-ротацию во время загрузки и уходит после', async () => {
    startLoading()
    const wrapper = mount(LoadingOverlay)
    await new Promise((resolve) => setTimeout(resolve, SETTLE_MS))

    expect(wrapper.find('.message').text()).toBeTruthy()
    // водяного знака Botify внизу больше нет — брендинг живёт только на витрине
    expect(wrapper.find('.brand').exists()).toBe(false)

    try {
      stopLoading()
      await new Promise((resolve) => setTimeout(resolve, SETTLE_MS))
      expect(wrapper.find('.overlay').exists()).toBe(false)
    } finally {
      stopLoading() // на случай падения первого assert'а — не оставить счётчик висеть
    }
  })

  it('среди ротации подписей есть Botifying…', () => {
    const wrapper = mount(LoadingOverlay)
    expect(wrapper.vm.messages).toContain('Botifying…')
  })
})
