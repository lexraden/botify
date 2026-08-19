<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchProducts, saveProduct } from '../api'

const route = useRoute()
const router = useRouter()
const error = ref('')
const saving = ref(false)

const form = ref({
  id: null,
  type: 'physical',
  title: '',
  description: '',
  image_url: '',
  price: '',
  digital_url: '',
  is_active: true,
})

onMounted(async () => {
  if (!route.params.id) return
  const products = await fetchProducts()
  const p = products.find((x) => x.id === Number(route.params.id))
  if (p) {
    form.value = {
      id: p.id,
      type: p.type,
      title: p.title,
      description: p.description || '',
      image_url: p.image_url || '',
      price: String(p.price),
      digital_url: p.digital_content?.url || '',
      is_active: p.is_active,
    }
  }
})

async function submit() {
  if (saving.value) return
  saving.value = true
  error.value = ''
  try {
    const f = form.value
    await saveProduct({
      id: f.id,
      type: f.type,
      title: f.title,
      description: f.description || null,
      image_url: f.image_url || null,
      price: f.price,
      digital_content: f.type !== 'physical' && f.digital_url ? { url: f.digital_url } : null,
      is_active: f.is_active,
    })
    router.push('/seller')
  } catch (e) {
    error.value = e.response?.data?.detail || 'Не удалось сохранить'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="form">
    <h2>{{ form.id ? 'Редактировать' : 'Новый товар / услуга' }}</h2>

    <label>Тип</label>
    <div class="types">
      <button
        v-for="(label, t) in { physical: '📦 Товар', digital: '📕 Digital', service: '🛎 Услуга' }"
        :key="t"
        :class="{ active: form.type === t }"
        @click="form.type = t"
      >{{ label }}</button>
    </div>

    <label>Название</label>
    <input v-model="form.title" maxlength="256" placeholder="Бургер / Гайд по крипте / Консультация" />

    <label>Описание</label>
    <textarea v-model="form.description" rows="3" placeholder="Что получит покупатель" />

    <label>Цена, USDT</label>
    <input v-model="form.price" inputmode="decimal" placeholder="9.99" />

    <label>Ссылка на изображение (опционально)</label>
    <input v-model="form.image_url" placeholder="https://…" />

    <template v-if="form.type !== 'physical'">
      <label>Ссылка для выдачи после оплаты</label>
      <input v-model="form.digital_url" placeholder="https://… (файл, документ, инвайт в чат)" />
    </template>

    <label class="check">
      <input type="checkbox" v-model="form.is_active" /> Показывать на витрине
    </label>

    <p v-if="error" class="error">{{ error }}</p>

    <div class="actions">
      <button class="secondary" @click="router.push('/seller')">Отмена</button>
      <button class="primary" :disabled="!form.title || !form.price || saving" @click="submit">
        {{ saving ? '…' : 'Сохранить' }}
      </button>
    </div>
  </div>
</template>

<style scoped lang="scss">
.form { padding: 16px; display: flex; flex-direction: column; }
label { font-size: 13px; opacity: 0.7; margin: 12px 0 4px; &.check { display: flex; gap: 8px; align-items: center; opacity: 1; } }
input:not([type='checkbox']), textarea {
  border: 1px solid var(--tg-theme-secondary-bg-color, #ddd);
  border-radius: 10px;
  padding: 10px;
  background: var(--tg-theme-bg-color, #fff);
  color: inherit;
  font: inherit;
}
.types {
  display: flex;
  gap: 8px;
  button {
    flex: 1;
    border: 1px solid var(--tg-theme-secondary-bg-color, #ddd);
    background: none;
    color: inherit;
    border-radius: 10px;
    padding: 10px 4px;
    cursor: pointer;
    &.active { border-color: var(--tg-theme-button-color, #2481cc); background: var(--tg-theme-secondary-bg-color, #eef6fd); }
  }
}
.error { color: #e74c3c; }
.actions {
  display: flex;
  gap: 8px;
  margin-top: 20px;
  button {
    flex: 1;
    border: 0;
    border-radius: 10px;
    padding: 14px;
    font-weight: 700;
    cursor: pointer;
    &.primary { background: var(--tg-theme-button-color, #2481cc); color: var(--tg-theme-button-text-color, #fff); &:disabled { opacity: 0.5; } }
    &.secondary { background: var(--tg-theme-secondary-bg-color, #f0f0f0); color: inherit; }
  }
}
</style>
