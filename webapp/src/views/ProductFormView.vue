<script setup>
import { onMounted, ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchProducts, saveProduct, uploadProductImage } from '../api'
import { t } from '../i18n'
import { apiError } from '../services/apiError'
import { MAX_PICK_MB } from '../services/imageCompress'

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

// --- вариации ---
// Заполнять заранее ничего не нужно: без нажатия «+» вариаций нет вовсе и в
// базе у товара не появляется ни одной строки. Нажал — сверху встаёт ряд
// пилюль, как у выбора типа товара, и поля ниже переключаются между ними.
const variants = ref([])
const active = ref(0)
const hasVariants = computed(() => form.value.type === 'physical' && variants.value.length > 0)
const current = computed(() => variants.value[active.value] || null)

function newVariant(from) {
  return {
    id: null,
    label: '',
    image_url: from?.image_url || '',
    price: from?.price || '',
    compare_at_price: '',
    stock: from?.stock ?? '',
  }
}

// Первое нажатие превращает уже заполненные поля товара в вариацию 1 и сразу
// добавляет вторую: иначе продавцу пришлось бы вводить то же самое заново.
function addVariant() {
  if (!variants.value.length) {
    variants.value.push(
      newVariant({
        image_url: form.value.image_url,
        price: form.value.price,
        stock: form.value.stock,
      }),
    )
  }
  variants.value.push(newVariant({ price: form.value.price }))
  active.value = variants.value.length - 1
}

function removeVariant(i) {
  variants.value.splice(i, 1)
  // одна вариация — это обычный товар: возвращаем её поля в форму
  if (variants.value.length === 1) {
    const only = variants.value[0]
    form.value.price = only.price
    form.value.stock = only.stock
    if (only.image_url) form.value.image_url = only.image_url
    variants.value = []
  }
  if (active.value >= variants.value.length) active.value = Math.max(0, variants.value.length - 1)
}

function variantTitle(v, i) {
  return String(v.label || '').trim() || t('form.variantN', { n: i + 1 })
}

// Подпись вариации — одно свободное поле («Красный, M»); в базе это словарь
// свойств с единственным ключом, формат от этого не меняется
function labelToAttributes(label) {
  const value = String(label).trim()
  return value ? { [t('form.variantAttr')]: value } : null
}

function attributesToLabel(attributes) {
  return Object.values(attributes || {})
    .map((x) => String(x).trim())
    .filter(Boolean)
    .join(', ')
}

// Фото вариации: тот же загрузчик и то же сжатие, что у главного фото товара
const variantFileInput = ref(null)
const uploadingVariant = ref(false)

async function onPickVariantImage(e) {
  const file = e.target.files?.[0]
  e.target.value = ''
  const v = current.value
  if (!file || !v) return
  imageError.value = ''
  if (file.size > MAX_IMAGE_MB * 1024 * 1024) {
    imageError.value = t('form.fileTooBig', { n: MAX_IMAGE_MB })
    return
  }
  uploadingVariant.value = true
  try {
    v.image_url = (await uploadProductImage(botId.value, file)).url
  } catch (err) {
    imageError.value = apiError(err, 'form.uploadError')
  } finally {
    uploadingVariant.value = false
  }
}

// кол-во на складе// кол-во на складе// кол-во на складе — целое от 0; пустое поле значит «не учитывать» (только у товаров)
const stockInvalid = computed(
  () =>
    form.value.type === 'physical' &&
    form.value.stock !== '' &&
    !/^\d+$/.test(form.value.stock),
)

// --- фото товара: выбор с устройства, превью, замена и удаление ---
const fileInput = ref(null)
const uploadingImage = ref(false)
const imageError = ref('')
// спиннер в маленьком окне: и пока файл грузится, и пока картинка не отрисовалась
const imgLoading = ref(false)
const MAX_IMAGE_MB = MAX_PICK_MB

watch(
  () => form.value.image_url,
  (v) => {
    imgLoading.value = !!v && !uploadingImage.value
  },
)

async function onPickImage(e) {
  const file = e.target.files?.[0]
  e.target.value = '' // повторный выбор того же файла должен срабатывать
  if (!file) return
  imageError.value = ''
  if (file.size > MAX_IMAGE_MB * 1024 * 1024) {
    imageError.value = t('form.fileTooBig', { n: MAX_IMAGE_MB })
    return
  }
  uploadingImage.value = true
  imgLoading.value = false // старую картинку убираем — место занимает спиннер
  try {
    const res = await uploadProductImage(botId.value, file)
    form.value.image_url = res.url
  } catch (err) {
    imageError.value = apiError(err, 'form.uploadError')
  } finally {
    uploadingImage.value = false
  }
}

function dropImage() {
  form.value.image_url = ''
}

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
      // В базе цена Numeric(18, 6), и наружу приходит «5.000000». В поле
      // редактирования это выглядит сбоем; Number() убирает хвост нулей —
      // ровно так цена и показывается везде на витрине.
      price: p.price == null ? '' : String(Number(p.price)),
      digital_url: p.digital_content?.url || '',
      stock: p.stock == null ? '' : String(p.stock),
      is_active: p.is_active,
    }
    // Одна вариация в базе — это обычный товар: её поля возвращаем в форму,
    // чтобы продавец увидел ровно то, что заполнял. Две и больше — пилюли.
    const saved = p.variants || []
    if (saved.length === 1) {
      const only = saved[0]
      form.value.price = only.price == null ? '' : String(Number(only.price))
      form.value.stock = only.stock == null ? '' : String(only.stock)
      if (only.images?.length) form.value.image_url = only.images[0]
    } else if (saved.length > 1) {
      variants.value = saved.map((v) => ({
        id: v.id,
        label: attributesToLabel(v.attributes),
        image_url: v.images?.[0] || '',
        price: v.price == null ? '' : String(Number(v.price)),
        compare_at_price:
          v.compare_at_price == null ? '' : String(Number(v.compare_at_price)),
        stock: v.stock == null ? '' : String(v.stock),
      }))
    }
  }
})

// Запятая как разделитель — самый естественный ввод с русской раскладки и с
// мобильной цифровой клавиатуры. Без нормализации сервер отвечал 422, а в
// форму печатался массив ошибок валидации Pydantic.
function normalPrice(raw) {
  const value = String(raw).trim().replace(',', '.')
  return /^\d+(\.\d{1,2})?$/.test(value) && Number(value) > 0 ? value : null
}

async function submit() {
  if (saving.value) return

  const basePrice = normalPrice(form.value.price)
  if (basePrice === null && !variants.value.length) {
    error.value = t('form.priceInvalid')
    return
  }

  // Вариации отправляем только когда их правда больше одной. Одна вариация
  // ничем не отличается от обычного товара, и заводить ради неё строку в базе
  // незачем.
  let payloadVariants = null
  let price = basePrice
  if (hasVariants.value) {
    const rows = variants.value.map((v) => ({
      ...v,
      price: normalPrice(v.price),
      compare: v.compare_at_price === '' ? null : normalPrice(v.compare_at_price),
    }))
    const bad = rows.findIndex((v) => v.price === null)
    if (bad !== -1) {
      active.value = bad
      error.value = t('form.priceInvalid')
      return
    }
    const noDiscount = rows.findIndex(
      (v) => v.compare !== null && Number(v.compare) <= Number(v.price),
    )
    if (noDiscount !== -1) {
      active.value = noDiscount
      error.value = t('form.compareInvalid')
      return
    }
    payloadVariants = rows.map((v) => ({
      id: v.id,
      sku: null,
      attributes: labelToAttributes(v.label),
      price: v.price,
      compare_at_price: v.compare,
      stock: v.stock === '' ? null : Number(v.stock),
      images: v.image_url ? [v.image_url] : null,
      is_active: true,
    }))
    // витринная цена товара — минимальная из вариаций; бэкенд пересчитает её
    // сам, но price в запросе обязателен
    price = payloadVariants.reduce(
      (min, v) => (min === null || Number(v.price) < Number(min) ? v.price : min),
      null,
    )
  }

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
      price,
      digital_content: f.type !== 'physical' && f.digital_url ? { url: f.digital_url } : null,
      // сток считаем только у товаров; у digital/услуг его нет
      stock: f.type === 'physical' && f.stock !== '' ? Number(f.stock) : null,
      is_active: f.is_active,
      // пустой список — вариации у товара убрали; null — их и не было
      variants: f.type === 'physical' ? payloadVariants || [] : [],
    })
    router.push(`/shop/${botId.value}`)
  } catch (e) {
    error.value = apiError(e, 'form.saveError')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="form">
    <h2>{{ form.id ? t('form.edit') : t('form.new') }}</h2>

    <!-- Порядок: название -> фото -> тип -> вариации -> поля вариации.
         Фото поднято сразу под название и сделано широким: продавец начинает
         с того, что у него уже есть в галерее, а не с выбора типа товара. -->
    <label>{{ t('form.titleLabel') }}</label>
    <input v-model="form.title" maxlength="256" :placeholder="t('form.titlePh')" />

    <label>{{ t('form.photoLabel') }}</label>
    <p class="hint">{{ t('form.photoHint') }}</p>
    <input
      ref="fileInput"
      type="file"
      accept="image/jpeg,image/png,image/webp,image/gif"
      hidden
      @change="onPickImage"
    />

    <button
      v-if="!form.image_url"
      class="drop-zone"
      type="button"
      :disabled="uploadingImage"
      @click="fileInput.click()"
    >
      <span class="drop-icon">+</span>
      <span>{{ uploadingImage ? t('form.uploading') : t('form.pickPhoto') }}</span>
    </button>

    <div v-else class="image-box wide">
      <div class="thumb big">
        <span v-if="uploadingImage || imgLoading" class="spinner" />
        <img
          v-show="!uploadingImage && !imgLoading"
          :src="form.image_url"
          :alt="t('form.photoAlt')"
          @load="imgLoading = false"
          @error="imgLoading = false"
        />
      </div>
      <div class="image-actions">
        <button class="btn btn-soft act" type="button" :disabled="uploadingImage" @click="fileInput.click()">
          {{ uploadingImage ? '…' : t('form.replace') }}
        </button>
        <button class="btn btn-soft act" type="button" @click="dropImage">{{ t('form.remove') }}</button>
      </div>
    </div>
    <p v-if="imageError" class="error">{{ imageError }}</p>

    <label>{{ t('form.typeLabel') }}</label>
    <div class="types">
      <button
        v-for="(label, key) in {
          physical: t('form.typePhysical'),
          digital: t('form.typeDigital'),
          service: t('form.typeService'),
        }"
        :key="key"
        :class="{ active: form.type === key }"
        @click="form.type = key"
      >{{ label }}</button>
    </div>

    <label>{{ t('form.descLabel') }}</label>
    <textarea v-model="form.description" rows="3" :placeholder="t('form.descPh')" />

    <!-- Ряд вариаций — такими же пилюлями, как выбор типа выше. Пока «+» не
         нажали, здесь одна кнопка и форма выглядит как обычная. -->
    <template v-if="form.type === 'physical'">
      <label>{{ t('form.variantsLabel') }}</label>
      <div class="types vrow">
        <button
          v-for="(v, i) in variants"
          :key="i"
          type="button"
          :class="{ active: i === active }"
          @click="active = i"
        >{{ variantTitle(v, i) }}</button>
        <button type="button" class="plus" @click="addVariant">
          + <template v-if="!variants.length">{{ t('form.addVariant') }}</template>
        </button>
      </div>
      <p v-if="!variants.length" class="hint">{{ t('form.variantsHint') }}</p>
    </template>

    <!-- Без вариаций — обычные поля товара -->
    <template v-if="!hasVariants">
      <label>{{ t('form.priceLabel') }}</label>
      <input v-model="form.price" inputmode="decimal" placeholder="9.99" />

      <template v-if="form.type === 'physical'">
        <label>{{ t('form.stockLabel') }}</label>
        <input v-model="form.stock" inputmode="numeric" :placeholder="t('form.stockPh')" />
        <p v-if="stockInvalid" class="error">{{ t('form.stockInvalid') }}</p>
      </template>
    </template>

    <!-- Поля выбранной вариации -->
    <div v-else-if="current" class="variant-card">
      <div class="variant-head">
        <b>{{ variantTitle(current, active) }}</b>
        <button type="button" class="link danger" @click="removeVariant(active)">
          {{ t('form.removeVariant') }}
        </button>
      </div>

      <label>{{ t('form.variantLabelField') }}</label>
      <input v-model="current.label" maxlength="64" :placeholder="t('form.variantLabelPh')" />

      <label>{{ t('form.photoLabel') }}</label>
      <input
        ref="variantFileInput"
        type="file"
        accept="image/jpeg,image/png,image/webp,image/gif"
        hidden
        @change="onPickVariantImage"
      />
      <button
        v-if="!current.image_url"
        class="drop-zone small"
        type="button"
        :disabled="uploadingVariant"
        @click="variantFileInput.click()"
      >
        <span class="drop-icon">+</span>
        <span>{{ uploadingVariant ? t('form.uploading') : t('form.pickPhoto') }}</span>
      </button>
      <div v-else class="image-box wide">
        <div class="thumb big"><img :src="current.image_url" :alt="current.label" /></div>
        <div class="image-actions">
          <button class="btn btn-soft act" type="button" @click="variantFileInput.click()">
            {{ uploadingVariant ? '…' : t('form.replace') }}
          </button>
          <button class="btn btn-soft act" type="button" @click="current.image_url = ''">
            {{ t('form.remove') }}
          </button>
        </div>
      </div>

      <label>{{ t('form.priceLabel') }}</label>
      <input v-model="current.price" inputmode="decimal" placeholder="9.99" />

      <label>{{ t('form.compareLabel') }}</label>
      <input v-model="current.compare_at_price" inputmode="decimal" placeholder="19.99" />
      <p class="hint">{{ t('form.compareHint') }}</p>

      <label>{{ t('form.stockLabel') }}</label>
      <input v-model="current.stock" inputmode="numeric" :placeholder="t('form.stockPh')" />
    </div>

    <template v-if="form.type !== 'physical'">
      <label>{{ t('form.digitalUrlLabel') }}</label>
      <input v-model="form.digital_url" placeholder="https://…" />
    </template>

    <label class="check">
      <input type="checkbox" v-model="form.is_active" /> {{ t('form.showOnStorefront') }}
    </label>

    <p v-if="error" class="error">{{ error }}</p>

    <div class="actions">
      <button class="btn btn-soft" @click="router.push(`/shop/${botId}`)">{{ t('common.cancel') }}</button>
      <button
        class="btn btn-primary"
        :disabled="!form.title || !form.price || stockInvalid || saving"
        @click="submit"
      >
        {{ saving ? '…' : t('form.save') }}
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
.hint { font-size: 12px; color: var(--sub); margin: -2px 0 10px; }
.image-box { display: flex; align-items: center; gap: 10px; }
.thumb {
  position: relative; width: 64px; height: 64px; border-radius: 13px;
  background: var(--surface2); overflow: hidden; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
}
.thumb img { width: 100%; height: 100%; object-fit: cover; }
.spinner {
  width: 22px; height: 22px; border-radius: 50%;
  border: 3px solid var(--border); border-top-color: var(--accent);
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
/* замена и удаление — рядом друг с другом справа от превью,
   чуть ниже самой картинки */
.image-actions { display: flex; flex: 1; gap: 8px; }
.image-actions .act { width: auto; height: 52px; padding: 0 18px; font-size: 15px; }
.error { color: var(--red); }
.actions { display: flex; gap: 8px; margin-top: 22px; }

/* Широкая зона загрузки сразу под названием: фото — первое, что продавец
   добавляет, и мелкая кнопка «выбрать» этому мешала */
.drop-zone {
  width: 100%; min-height: 132px; border-radius: 15px;
  border: 1.5px dashed var(--accent); background: var(--accent-soft);
  color: var(--accent); font-size: 14px; font-weight: 700; cursor: pointer;
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px;
}
.drop-icon { font-size: 30px; font-weight: 700; line-height: 1; }
.image-box.wide { width: 100%; }
.thumb.big { width: 100%; height: 168px; border-radius: 15px; overflow: hidden; }
.thumb.big img { width: 100%; height: 100%; object-fit: cover; }

.variant-card {
  border: 1.5px solid var(--line, var(--border)); border-radius: 15px;
  padding: 12px 13px 14px; margin-top: 4px; background: var(--surface2);
}
.variant-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px; }
.link { border: 0; background: none; color: var(--accent); font-size: 13px; font-weight: 700; cursor: pointer; padding: 4px 0; }
.link.danger { color: var(--red); }
/* Ряд вариаций — тот же ритм, что у выбора типа выше: вертикальный отступ
   обязан совпадать с .types button, иначе кнопки схлопываются до высоты
   строки и ряд перестаёт читаться как продолжение типа товара */
.vrow { flex-wrap: wrap; }
.vrow button { flex: 0 1 auto; padding: 11px 15px; }
.vrow .plus {
  border-style: dashed; border-color: var(--accent); color: var(--accent);
  padding: 11px 18px;
}
.legacy-add {
  width: 100%; margin-top: 10px; padding: 13px; border-radius: 14px;
  border: 1.5px dashed var(--accent); background: var(--accent-soft);
  color: var(--accent); font-size: 14px; font-weight: 700; cursor: pointer;
  display: flex; align-items: center; justify-content: center; gap: 8px;
}
.add-variant .drop-icon { font-size: 20px; }
.drop-zone.small { min-height: 96px; }
</style>
