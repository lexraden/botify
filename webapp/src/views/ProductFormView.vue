<script setup>
import { onMounted, ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchProducts, saveProduct, uploadProductImage } from '../api'
import { t } from '../i18n'
import { apiError } from '../services/apiError'
import { MAX_PICK_MB } from '../services/imageCompress'
import VariantTabs from '../components/VariantTabs.vue'

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
// Товар либо без них (цена и остаток на нём самом — так было всегда), либо с
// ними, и тогда цена, остаток и фото живут в вариации. Витринные price/stock
// товара бэкенд пересчитывает сам при сохранении, поэтому здесь их не трогаем.
//
// Свойства («Цвет: Красный») редактируются массивом пар, а не объектом:
// в объекте две пустых строки схлопнулись бы в одну, а пустое имя нельзя
// было бы править. В объект набор превращается только при сохранении.
const variants = ref([])
const activeVariant = ref(0)
const hasVariants = computed(() => form.value.type === 'physical' && variants.value.length > 0)
const current = computed(() => variants.value[activeVariant.value] || null)
const MAX_ATTRS = 6

function blankVariant() {
  // новая вариация наследует базовые данные товара — продавцу остаётся
  // поправить только то, чем она отличается
  return {
    id: null,
    sku: '',
    attrs: [{ name: '', value: '' }],
    price: form.value.price || '',
    compare_at_price: '',
    stock: form.value.stock || '',
    images: form.value.image_url ? [form.value.image_url] : [],
    is_active: true,
  }
}

function addVariant() {
  variants.value.push(blankVariant())
  activeVariant.value = variants.value.length - 1
}

function removeVariant(i) {
  variants.value.splice(i, 1)
  if (activeVariant.value >= variants.value.length) {
    activeVariant.value = Math.max(0, variants.value.length - 1)
  }
}

function addAttr(variant) {
  if (variant.attrs.length < MAX_ATTRS) variant.attrs.push({ name: '', value: '' })
}

function dropAttr(variant, i) {
  variant.attrs.splice(i, 1)
  if (!variant.attrs.length) variant.attrs.push({ name: '', value: '' })
}

// подпись вариации для вкладки — только заполненные свойства
function attrsObject(variant) {
  const out = {}
  for (const { name, value } of variant.attrs) {
    const key = String(name).trim()
    const val = String(value).trim()
    if (key && val) out[key] = val
  }
  return Object.keys(out).length ? out : null
}

// вкладкам нужен объект свойств — считаем его на лету
const tabVariants = computed(() =>
  variants.value.map((v) => ({ attributes: attrsObject(v), is_active: v.is_active })),
)

// Фото вариации: загружаются в ту, что открыта сейчас. Тот же загрузчик и то
// же сжатие, что у главного фото товара — путь один на всё приложение.
const variantFileInput = ref(null)
const uploadingVariantImage = ref(false)
const MAX_VARIANT_IMAGES = 8

async function onPickVariantImage(e) {
  const files = Array.from(e.target.files || [])
  e.target.value = ''
  const variant = current.value
  if (!files.length || !variant) return
  imageError.value = ''
  const room = MAX_VARIANT_IMAGES - variant.images.length
  if (room <= 0) return
  uploadingVariantImage.value = true
  try {
    for (const file of files.slice(0, room)) {
      if (file.size > MAX_IMAGE_MB * 1024 * 1024) {
        imageError.value = t('form.fileTooBig', { n: MAX_IMAGE_MB })
        continue
      }
      const res = await uploadProductImage(botId.value, file)
      variant.images.push(res.url)
    }
  } catch (err) {
    imageError.value = apiError(err, 'form.uploadError')
  } finally {
    uploadingVariantImage.value = false
  }
}

function dropVariantImage(i) {
  current.value?.images.splice(i, 1)
}

// кол-во на складе — целое от 0; пустое поле значит «не учитывать» (только у товаров)
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
    variants.value = (p.variants || []).map((v) => ({
      id: v.id,
      sku: v.sku || '',
      attrs: Object.entries(v.attributes || {}).map(([name, value]) => ({ name, value })) || [],
      price: v.price == null ? '' : String(Number(v.price)),
      compare_at_price: v.compare_at_price == null ? '' : String(Number(v.compare_at_price)),
      stock: v.stock == null ? '' : String(v.stock),
      images: [...(v.images || [])],
      is_active: v.is_active !== false,
    }))
    // у вариации без свойств должна остаться пустая строка для ввода
    for (const v of variants.value) {
      if (!v.attrs.length) v.attrs.push({ name: '', value: '' })
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

  // У товара с вариациями цена и остаток берутся из них: витринные price и
  // stock товара бэкенд пересчитает сам. Но price в запросе обязателен, так
  // что шлём минимальную — она же и окажется в ответе.
  let price = normalPrice(form.value.price)
  const payloadVariants = hasVariants.value
    ? variants.value.map((v) => ({
        id: v.id,
        sku: v.sku || null,
        attributes: attrsObject(v),
        price: normalPrice(v.price),
        compare_at_price: v.compare_at_price === '' ? null : normalPrice(v.compare_at_price),
        stock: v.stock === '' ? null : Number(v.stock),
        images: v.images.length ? v.images : null,
        is_active: v.is_active,
      }))
    : null

  if (payloadVariants) {
    const bad = payloadVariants.findIndex((v) => v.price === null)
    if (bad !== -1) {
      activeVariant.value = bad
      error.value = t('form.priceInvalid')
      return
    }
    const noDiscount = payloadVariants.findIndex(
      (v) => v.compare_at_price !== null && Number(v.compare_at_price) <= Number(v.price),
    )
    if (noDiscount !== -1) {
      activeVariant.value = noDiscount
      error.value = t('form.compareInvalid')
      return
    }
    price = payloadVariants.reduce(
      (min, v) => (min === null || Number(v.price) < Number(min) ? v.price : min),
      null,
    )
  }

  if (price === null) {
    error.value = t('form.priceInvalid')
    return
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

    <!-- Вариации только у физического товара: у услуги или файла нет ни
         размера, ни цвета — бэкенд их для остальных типов и не принимает. -->
    <template v-if="form.type === 'physical'">
      <label>{{ t('form.variantsLabel') }}</label>
      <p class="hint">{{ t('form.variantsHint') }}</p>
      <VariantTabs
        :variants="tabVariants"
        :active="activeVariant"
        @select="activeVariant = $event"
        @add="addVariant"
      />
    </template>

    <!-- Без вариаций цена и остаток живут на самом товаре, как и раньше -->
    <template v-if="!hasVariants">
      <label>{{ t('form.priceLabel') }}</label>
      <input v-model="form.price" inputmode="decimal" placeholder="9.99" />

      <template v-if="form.type === 'physical'">
        <label>{{ t('form.stockLabel') }}</label>
        <input v-model="form.stock" inputmode="numeric" :placeholder="t('form.stockPh')" />
        <p v-if="stockInvalid" class="error">{{ t('form.stockInvalid') }}</p>
      </template>
    </template>

    <!-- Поля открытой вариации -->
    <div v-else-if="current" class="variant-card">
      <div class="variant-head">
        <b>{{ t('form.variantN', { n: activeVariant + 1 }) }}</b>
        <button type="button" class="link danger" @click="removeVariant(activeVariant)">
          {{ t('form.removeVariant') }}
        </button>
      </div>

      <label>{{ t('form.attrsLabel') }}</label>
      <div v-for="(row, i) in current.attrs" :key="i" class="attr-row">
        <input v-model="row.name" maxlength="64" :placeholder="t('form.attrNamePh')" />
        <input v-model="row.value" maxlength="64" :placeholder="t('form.attrValuePh')" />
        <button type="button" class="drop" :aria-label="t('form.remove')" @click="dropAttr(current, i)">✕</button>
      </div>
      <button
        v-if="current.attrs.length < MAX_ATTRS"
        type="button"
        class="link"
        @click="addAttr(current)"
      >{{ t('form.addAttr') }}</button>

      <label>{{ t('form.priceLabel') }}</label>
      <input v-model="current.price" inputmode="decimal" placeholder="9.99" />

      <label>{{ t('form.compareLabel') }}</label>
      <p class="hint">{{ t('form.compareHint') }}</p>
      <input v-model="current.compare_at_price" inputmode="decimal" placeholder="19.99" />

      <label>{{ t('form.stockLabel') }}</label>
      <input v-model="current.stock" inputmode="numeric" :placeholder="t('form.stockPh')" />

      <label>{{ t('form.skuLabel') }}</label>
      <input v-model="current.sku" maxlength="64" :placeholder="t('form.skuPh')" />

      <label>{{ t('form.variantPhotos') }}</label>
      <input
        ref="variantFileInput"
        type="file"
        accept="image/jpeg,image/png,image/webp,image/gif"
        multiple
        hidden
        @change="onPickVariantImage"
      />
      <div class="gallery">
        <div v-for="(url, i) in current.images" :key="url + i" class="shot">
          <img :src="url" alt="" />
          <button type="button" class="drop" :aria-label="t('form.remove')" @click="dropVariantImage(i)">✕</button>
        </div>
        <button
          v-if="current.images.length < MAX_VARIANT_IMAGES"
          type="button"
          class="shot add"
          :disabled="uploadingVariantImage"
          @click="variantFileInput.click()"
        >{{ uploadingVariantImage ? '…' : '+' }}</button>
      </div>

      <label class="check">
        <input type="checkbox" v-model="current.is_active" /> {{ t('form.variantActive') }}
      </label>
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
</style>
