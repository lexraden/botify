<script setup>
import { onUnmounted, ref, watch } from 'vue'
import { isLoading } from '../services/loading'

// Пока идёт загрузка, подпись под спиннером меняется — так ожидание
// читается как работа, а не как зависший экран
const MESSAGES = [
  'Собираем данные…',
  'Загружаем бота…',
  'Подключаем базу…',
  'Готовим витрину…',
  'Считаем статистику…',
  'Синхронизируем заказы…',
  'Проверяем каталог…',
  'Обновляем базу клиентов…',
  'Шифруем соединение…',
  'Почти готово…',
]
const STEP_MS = 1400

// Подписи идут вразнобой, но подряд одна и та же не повторяется
function pickMessage(previous) {
  const pool = MESSAGES.filter((m) => m !== previous)
  return pool[Math.floor(Math.random() * pool.length)]
}

const message = ref(pickMessage(null))
let timer = null

function startCycling() {
  message.value = pickMessage(null)
  timer = setInterval(() => {
    message.value = pickMessage(message.value)
  }, STEP_MS)
}

function stopCycling() {
  if (timer !== null) {
    clearInterval(timer)
    timer = null
  }
}

watch(isLoading, (value) => (value ? startCycling() : stopCycling()), { immediate: true })
onUnmounted(stopCycling)
</script>

<template>
  <Transition name="fade">
    <div v-if="isLoading" class="overlay">
      <div class="spinner" />
      <Transition name="swap" mode="out-in">
        <div :key="message" class="message">{{ message }}</div>
      </Transition>
    </div>
  </Transition>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  background: color-mix(in srgb, var(--bg) 60%, transparent);
  backdrop-filter: blur(2px);
}
.spinner {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  border: 3px solid var(--surface2);
  border-top-color: var(--accent);
  animation: spin 0.7s linear infinite;
}
.message {
  font-size: 14px;
  font-weight: 700;
  color: var(--sub);
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
.fade-enter-active, .fade-leave-active { transition: opacity 0.15s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
.swap-enter-active, .swap-leave-active { transition: opacity 0.25s ease, transform 0.25s ease; }
.swap-enter-from { opacity: 0; transform: translateY(6px); }
.swap-leave-to { opacity: 0; transform: translateY(-6px); }
</style>
