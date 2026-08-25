import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import LoadingOverlay from '../LoadingOverlay.vue'
import { startLoading, stopLoading } from '../../services/loading'

// оверлей показывается с задержкой SHOW_AFTER_MS (150 мс), исчезает после
// fade-перехода — в обоих случаях ждём с запасом
const SETTLE_MS = 300

describe('LoadingOverlay — бренд платформы', () => {
  it('во время загрузки виден знак Botify и подпись-ротация', async () => {
    startLoading()
    const wrapper = mount(LoadingOverlay)
    await new Promise((resolve) => setTimeout(resolve, SETTLE_MS))

    expect(wrapper.find('.brand').text()).toBe('Botify')
    expect(wrapper.find('.message').text()).toBeTruthy()

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
