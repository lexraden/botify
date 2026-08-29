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

// --- дополнительные вариации ---
// Заполнять ничего заранее не нужно: обычная форма — это и есть товар (он же
// первая вариация). Нажали «+» — снизу открылся такой же блок: подпись, фото,
// цена, остаток. Не нажали — товар сохраняется как раньше, без вариаций
// вовсе, и в базе у него не появляется ни одной строки.
const extras = ref([])
// id первой вариации и её подпись: базовые поля формы — это она и есть
const baseVariantId = ref(null)
const baseLabel = ref('')
const hasVariants = computed(() => form.value.type === 'physical' && extras.value.length > 0)

function addVariant() {
  extras.value.push({
    id: null,
    label: '',
    image_url: '',
    price: form.value.price || '',
    stock: form.value.stock || '',
  })
}

function removeVariant(i) {
  extras.value.splice(i, 1)
}

// Подпись вариации — одно свободное поле («Красный, M»), а не набор пар:
// в базе это по-прежнему словарь свойств, просто с единственным ключом
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
const extraFileInput = ref(null)
const uploadingFor = ref(null) // индекс блока, у которого идёт загрузка

async function onPickExtraImage(e) {
  const file = e.target.files?.[0]
  e.target.value = ''
  const i = uploadingFor.value
  const variant = extras.value[i]
  if (!file || !variant) {
    uploadingFor.value = null
    return
  }
  imageError.value = ''
  if (file.size > MAX_IMAGE_MB * 1024 * 1024) {
    imageError.value = t('form.fileTooBig', { n: MAX_IMAGE_MB })
    uploadingFor.value = null
    return
  }
  try {
    const res = await uploadProductImage(botId.value, file)
    variant.image_url = res.url
  } catch (err) {
    imageError.value = apiError(err, 'form.uploadError')
  } finally {
    uploadingFor.value = null
  }
}

function pickExtraImage(i) {
  uploadingFor.value = i
  extraFileInput.value.click()
}

// кол-во на складе// кол-во на складе — целое от 0; пустое поле значит «не учитывать» (только у товаров)
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
    // Первая вариация — это и есть базовые поля формы; остальные ложатся
    // блоками ниже. Так продавец видит ровно то же, что заполнял.
    const saved = p.variants || []
    if (saved.length) {
      const [first, ...rest] = saved
      form.value.price = first.price == null ? '' : String(Number(first.price))
      form.value.stock = first.stock == null ? '' : String(first.stock)
      if (first.images?.length) form.value.image_url = first.images[0]
      baseVariantId.value = first.id
      baseLabel.value = attributesToLabel(first.attributes)
      extras.value = rest.map((v) => ({
        id: v.id,
        label: attributesToLabel(v.attributes),
        image_url: v.images?.[0] || '',
        price: v.price == null ? '' : String(Number(v.price)),
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
  if (basePrice === null) {
    error.value = t('form.priceInvalid')
    return
  }

  // Вариации отправляем только если продавец нажимал «+». Первая — это
  // базовые поля формы: их же он и заполнял как обычно.
  let payloadVariants = null
  let price = basePrice
  if (hasVariants.value) {
    const rows = [
      {
        id: baseVariantId.value,
        label: baseLabel.value,
        price: basePrice,
        stock: form.value.stock,
        image_url: form.value.image_url,
      },
      ...extras.value.map((v) => ({ ...v, price: normalPrice(v.price) })),
    ]
    const bad = rows.findIndex((v) => v.price === null)
    if (bad !== -1) {
      error.value = t('form.priceInvalid')
      return
    }
    payloadVariants = rows.map((v) => ({
      id: v.id,
      sku: null,
      attributes: labelToAttributes(v.label),
      price: v.price,
      compare_at_price: null,
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

    <!-- Цена и остаток — как обычно. Если продавец добавит вариации, эти же
         поля станут первой из них: заполнять заранее ничего не нужно. -->
    <template v-if="hasVariants">
      <label>{{ t('form.variantLabelField') }}</label>
      <input v-model="baseLabel" maxlength="64" :placeholder="t('form.variantLabelPh')" />
    </template>

    <label>{{ t('form.priceLabel') }}</label>
    <input v-model="form.price" inputmode="decimal" placeholder="9.99" />

    <template v-if="form.type === 'physical'">
      <label>{{ t('form.stockLabel') }}</label>
      <input v-model="form.stock" inputmode="numeric" :placeholder="t('form.stockPh')" />
      <p v-if="stockInvalid" class="error">{{ t('form.stockInvalid') }}</p>
    </template>

    <!-- Дополнительные вариации: такой же блок, только ниже -->
    <template v-if="form.type === 'physical'">
      <input
        ref="extraFileInput"
        type="file"
        accept="image/jpeg,image/png,image/webp,image/gif"
        hidden
        @change="onPickExtraImage"
      />

      <div v-for="(v, i) in extras" :key="i" class="variant-card">
        <div class="variant-head">
          <b>{{ t('form.variantN', { n: i + 2 }) }}</b>
          <button type="button" class="link danger" @click="removeVariant(i)">
            {{ t('form.removeVariant') }}
          </button>
        </div>

        <label>{{ t('form.variantLabelField') }}</label>
        <input v-model="v.label" maxlength="64" :placeholder="t('form.variantLabelPh')" />

        <label>{{ t('form.photoLabel') }}</label>
        <button
          v-if="!v.image_url"
          class="drop-zone small"
          type="button"
          :disabled="uploadingFor === i"
          @click="pickExtraImage(i)"
        >
          <span class="drop-icon">+</span>
          <span>{{ uploadingFor === i ? t('form.uploading') : t('form.pickPhoto') }}</span>
        </button>
        <div v-else class="image-box wide">
          <div class="thumb big"><img :src="v.image_url" :alt="v.label" /></div>
          <div class="image-actions">
            <button class="btn btn-soft act" type="button" @click="pickExtraImage(i)">
              {{ uploadingFor === i ? '…' : t('form.replace') }}
            </button>
            <button class="btn btn-soft act" type="button" @click="v.image_url = ''">
              {{ t('form.remove') }}
            </button>
          </div>
        </div>

        <label>{{ t('form.priceLabel') }}</label>
        <input v-model="v.price" inputmode="decimal" placeholder="9.99" />

        <label>{{ t('form.stockLabel') }}</label>
        <input v-model="v.stock" inputmode="numeric" :placeholder="t('form.stockPh')" />
      </div>

      <button type="button" class="add-variant" @click="addVariant">
        <span class="drop-icon">+</span>
        <span>{{ t('form.addVariant') }}</span>
      </button>
      <p class="hint">{{ t('form.variantsHint') }}</p>
    </template>

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
.attr-row { display: flex; gap: 6px; align-items: center; margin-bottom: 6px; }
.attr-row input { flex: 1; min-width: 0; }
.drop {
  flex: 0 0 auto; width: 30px; height: 30px; border-radius: 9px; border: 0;
  background: var(--surface); color: var(--sub); cursor: pointer; font-size: 13px;
}
.gallery { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 2px; }
.shot { position: relative; width: 68px; height: 68px; border-radius: 12px; overflow: hidden; }
.shot img { width: 100%; height: 100%; object-fit: cover; }
.shot .drop { position: absolute; top: 3px; right: 3px; width: 22px; height: 22px; background: rgba(0,0,0,0.55); color: #fff; }
.shot.add {
  border: 1.5px dashed var(--accent); background: var(--accent-soft);
  color: var(--accent); font-size: 22px; font-weight: 700; cursor: pointer;
}
.add-variant {
  width: 100%; margin-top: 10px; padding: 13px; border-radius: 14px;
  border: 1.5px dashed var(--accent); background: var(--accent-soft);
  color: var(--accent); font-size: 14px; font-weight: 700; cursor: pointer;
  display: flex; align-items: center; justify-content: center; gap: 8px;
}
.add-variant .drop-icon { font-size: 20px; }
.drop-zone.small { min-height: 96px; }
</style>
