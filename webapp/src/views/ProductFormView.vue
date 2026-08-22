<script setup>
import { onMounted, ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchProducts, saveProduct } from '../api'

const route = useRoute()
const router = useRouter()
const botId = computed(() => route.params.botId)
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
  stock: '', // пусто — без ограничения
  is_active: true,
})

// кол-во на складе — целое от 0; пустое поле значит «не учитывать» (только у товаров)
const stockInvalid = computed(
  () =>
    form.value.type === 'physical' &&
    form.value.stock !== '' &&
    !/^\d+$/.test(form.value.stock),
)

onMounted(async () => {
  if (!route.params.id) return
  const products = await fetchProducts(botId.value)
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
      stock: p.stock == null ? '' : String(p.stock),
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
    await saveProduct(botId.value, {
      id: f.id,
      type: f.type,
      title: f.title,
      description: f.description || null,
      image_url: f.image_url || null,
      price: f.price,
      digital_content: f.type !== 'physical' && f.digital_url ? { url: f.digital_url } : null,
      // сток считаем только у товаров; у digital/услуг его нет
      stock: f.type === 'physical' && f.stock !== '' ? Number(f.stock) : null,
      is_active: f.is_active,
    })
    router.push(`/shop/${botId.value}`)
  } catch (e) {
    error.value = e.response?.data?.detail || 'Не удалось сохранить'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="form">
    <h2>{{ form.id ? 'Редактировать' : 'Новый товар или услуга' }}</h2>

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
    <input v-model="form.title" maxlength="256" placeholder="Капучино / Гайд по обжарке" />

    <label>Описание</label>
    <textarea v-model="form.description" rows="3" placeholder="Что получит покупатель" />

    <label>Цена, USDT</label>
    <input v-model="form.price" inputmode="decimal" placeholder="9.99" />

    <template v-if="form.type === 'physical'">
      <label>Кол-во на складе</label>
      <input v-model="form.stock" inputmode="numeric" placeholder="пусто — без ограничения" />
      <p v-if="stockInvalid" class="error">Кол-во — целое число или пустое поле.</p>
    </template>

    <label>Ссылка на изображение (опционально)</label>
    <input v-model="form.image_url" placeholder="https://…" />

    <template v-if="form.type !== 'physical'">
      <label>Ссылка для выдачи после оплаты</label>
      <input v-model="form.digital_url" placeholder="https://… (файл, инвайт в чат)" />
    </template>

    <label class="check">
      <input type="checkbox" v-model="form.is_active" /> Показывать на витрине
    </label>

    <p v-if="error" class="error">{{ error }}</p>

    <div class="actions">
      <button class="btn btn-soft" @click="router.push(`/shop/${botId}`)">Отмена</button>
      <button
        class="btn btn-primary"
        :disabled="!form.title || !form.price || stockInvalid || saving"
        @click="submit"
      >
        {{ saving ? '…' : 'Сохранить' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.form { padding: 18px 16px 36px; display: flex; flex-direction: column; }
h2 { font-size: 18px; margin: 0 0 8px; }
label { font-size: 12px; color: var(--sub); margin: 12px 0 5px; font-weight: 700; }
label.check { display: flex; gap: 10px; align-items: center; color: var(--text); }
label.check input { width: auto; }
textarea { resize: none; }
.types { display: flex; gap: 8px; }
.types button {
  flex: 1; border: 1px solid var(--border); background: var(--surface); color: var(--text);
  border-radius: 13px; padding: 11px 4px; cursor: pointer; font-weight: 700; font-size: 14px;
}
.types button.active { border-color: var(--accent); background: var(--accent-soft); color: var(--accent); }
.error { color: var(--red); }
.actions { display: flex; gap: 8px; margin-top: 22px; }
</style>
