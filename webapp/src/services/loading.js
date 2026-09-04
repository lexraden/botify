import { computed, ref } from 'vue'

// Счётчик запросов в полёте — оверлей показывается, пока он больше нуля.
const pending = ref(0)
// Небольшая задержка, чтобы быстрые ответы не давали мигание спиннера
const SHOW_AFTER_MS = 150
const visible = ref(false)
let timer = null

function sync() {
  if (pending.value > 0) {
    if (timer === null && !visible.value) {
      timer = setTimeout(() => {
        visible.value = true
        timer = null
      }, SHOW_AFTER_MS)
    }
  } else {
    if (timer !== null) {
      clearTimeout(timer)
      timer = null
    }
    visible.value = false
  }
}

export function startLoading() {
  pending.value += 1
  sync()
}

export function stopLoading() {
  pending.value = Math.max(0, pending.value - 1)
  sync()
}

export const isLoading = computed(() => visible.value)
