<script setup>
import { onMounted, ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchProducts, saveProduct, uploadProductImage } from '../api'
import { t } from '../i18n'
import { apiError, isPlanLimit } from '../services/apiError'
import PlanModal from '../components/PlanModal.vue'
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
  compare_at_price: '',
  digital_url: '',
  stock: '', // пусто — без ограничения
  is_active: true,
})

// --- вариации ---
// Вариация 1 — это сам товар: поля формы и есть её поля. Пока «+» не нажали,
// вариаций в базе нет вовсе, и товар сохраняется ровно как раньше.
const variants = ref([])
const active = ref(0)
const hasVariants = computed(() => form.value.type === 'physical' && variants.value.length > 0)

// Куда пишут поля цены, старой цены, остатка и фото: в сам товар, пока
// вариаций нет, и в выбранную вариацию, когда они есть. Один прокси вместо
// двух копий этих полей в разметке — копии разъехались бы на первой правке.
// Имена полей у товара и у вариации совпадают намеренно, ради этой строки.
const slot = computed(() =>
  hasVariants.value ? variants.value[active.value] || form.value : form.value,
)

// Квадратики сверху: V1, V2… Полное название вариации — в подсказке, чтобы
// сам переключатель оставался мелким и не разъезжался на три строки.
function slotTitle(i) {
  const v = variants.value[i]
  return String(v?.label || '').trim() || t('form.variantN', { n: i + 1 })
}

function newVariant(from) {
  return {
    id: null,
    label: '',
    // название и описание чаще общие, чем разные, — переносим их в новую
    // вариацию, а расходится обычно то, что ниже: цена, фото, остаток
    title: from?.title || '',
    description: from?.description || '',
    image_url: from?.image_url || '',
    price: from?.price || '',
    compare_at_price: from?.compare_at_price || '',
    stock: from?.stock ?? '',
  }
}

// «+» добавляет ровно одну вариацию — ту, на которую и переключает. Первое
// нажатие вдобавок забирает уже заполненные поля товара под V1: продавец их
// только что ввёл, и заставлять его вводить то же самое заново незачем.
function addVariant() {
  if (!variants.value.length) variants.value.push(newVariant(form.value))
  variants.value.push(newVariant({ title: form.value.title, description: form.value.description }))
  active.value = variants.value.length - 1
}

function removeVariant(i) {
  variants.value.splice(i, 1)
  // осталась одна — это снова обычный товар: её поля возвращаем в форму
  if (variants.value.length === 1) {
    const only = variants.value[0]
    if (only.title) form.value.title = only.title
    form.value.description = only.description
    form.value.price = only.price
    form.value.compare_at_price = only.compare_at_price
    form.value.stock = only.stock
    if (only.image_url) form.value.image_url = only.image_url
    variants.value = []
  }
  if (active.value >= variants.value.length) active.value = Math.max(0, variants.value.length - 1)
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

// кол-во на складе — целое от 0; пустое поле значит «не учитывать» (только у товаров)
const stockInvalid = computed(
  () =>
    form.value.type === 'physical' &&
    slot.value.stock !== '' &&
    !/^\d+$/.test(slot.value.stock),
)

// --- фото товара: выбор с устройства, превью, замена и удаление ---
const fileInput = ref(null)
const uploadingImage = ref(false)
const imageError = ref('')
// спиннер в маленьком окне: и пока файл грузится, и пока картинка не отрисовалась
const imgLoading = ref(false)
// раскрыты ли действия поверх фото; закрываются сами при любой смене картинки
// и при переключении вариации — иначе висят над чужим фото
const photoMenu = ref(false)
// какой лимит упёрся: 'products' | 'services' | null
const planLimit = ref(null)
const MAX_IMAGE_MB = MAX_PICK_MB

watch(
  () => slot.value.image_url,
  (v) => {
    imgLoading.value = !!v && !uploadingImage.value
    photoMenu.value = false
  },
)

// Предупреждение живёт до правки, а не до следующего нажатия «Сохранить».
// Без этого продавец исправлял цену и продолжал видеть «Цена — число больше
// нуля» над уже верным полем — сообщение выглядело как баг формы.
watch([form, variants], () => { error.value = '' }, { deep: true })

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
    slot.value.image_url = res.url
  } catch (err) {
    imageError.value = apiError(err, 'form.uploadError')
  } finally {
    uploadingImage.value = false
  }
}

function dropImage() {
  slot.value.image_url = ''
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
      compare_at_price:
        p.compare_at_price == null ? '' : String(Number(p.compare_at_price)),
      digital_url: p.digital_content?.url || '',
      stock: p.stock == null ? '' : String(p.stock),
      is_active: p.is_active,
    }
    // Одна вариация в базе — это обычный товар: её поля возвращаем в форму,
    // чтобы продавец увидел ровно то, что заполнял. Две и больше — пилюли.
    const saved = p.variants || []
    if (saved.length === 1) {
      const only = saved[0]
      if (only.title) form.value.title = only.title
      if (only.description) form.value.description = only.description
      form.value.price = only.price == null ? '' : String(Number(only.price))
      form.value.compare_at_price =
        only.compare_at_price == null ? '' : String(Number(only.compare_at_price))
      form.value.stock = only.stock == null ? '' : String(only.stock)
      if (only.images?.length) form.value.image_url = only.images[0]
    } else if (saved.length > 1) {
      variants.value = saved.map((v) => ({
        id: v.id,
        label: attributesToLabel(v.attributes),
        // NULL в базе — у вариации своего названия нет: показываем товарное,
        // иначе поле открылось бы пустым и сохранение стёрло бы название
        title: v.title || p.title,
        description: v.description || '',
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
  if (basePrice === null && !hasVariants.value) {
    error.value = t('form.priceInvalid')
    return
  }

  // Старая цена товара без вариаций — то же правило, что и у вариации:
  // зачёркнутое число обязано быть выше текущего, иначе это не скидка
  let baseCompare = null
  if (!hasVariants.value && form.value.compare_at_price !== '') {
    baseCompare = normalPrice(form.value.compare_at_price)
    if (baseCompare === null || Number(baseCompare) <= Number(basePrice)) {
      error.value = t('form.compareInvalid')
      return
    }
  }

  // Вариации отправляем только когда их правда больше одной. Одна вариация
  // ничем не отличается от обычного товара, и заводить ради неё строку в базе
  // незачем.
  let payloadVariants = null
  let price = basePrice
  let image = form.value.image_url
  let title = form.value.title
  let description = form.value.description || null
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
    // Название есть у каждой вариации: пустое ушло бы на витрину пустой
    // строкой, а у товара оно взялось бы от первой — и покупатель увидел
    // безымянный вариант рядом с названным
    const unnamed = rows.findIndex((v) => !String(v.title).trim())
    if (unnamed !== -1) {
      active.value = unnamed
      error.value = t('form.titleRequired')
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
      title: String(v.title).trim(),
      description: v.description?.trim() || null,
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
    // Витрина и карточка читают products.image_url и про вариации не знают.
    // Берём фото первой вариации: продавец правит его там же, где цену, и
    // ждёт, что карточка покажет именно его, а не снимок с момента «+».
    image = rows.find((v) => v.image_url)?.image_url || image
    // Название и описание товара — от первой вариации: в форме она и есть сам
    // товар. Их читают карточка в сетке, заказы и уведомления, и про вариации
    // они не знают (см. app/services/variants.py)
    title = String(rows[0].title).trim()
    description = rows[0].description?.trim() || null
  }

  saving.value = true
  error.value = ''
  try {
    const f = form.value
    await saveProduct(botId.value, {
      id: f.id,
      type: f.type,
      title,
      description,
      image_url: image || null,
      price,
      // у товара с вариациями скидка своя у каждой — бэкенд обнулит это поле
      compare_at_price: baseCompare,
      digital_content: f.type !== 'physical' && f.digital_url ? { url: f.digital_url } : null,
      // сток считаем только у товаров; у digital/услуг его нет
      stock: f.type === 'physical' && f.stock !== '' ? Number(f.stock) : null,
      is_active: f.is_active,
      // пустой список — вариации у товара убрали; null — их и не было
      variants: f.type === 'physical' ? payloadVariants || [] : [],
    })
    router.push(`/shop/${botId.value}`)
  } catch (e) {
    // Лимит бесплатного тарифа — не ошибка ввода: показываем тарифы, а не
    // красную строку под формой, из которой непонятно, что делать
    if (isPlanLimit(e)) planLimit.value = form.value.type === 'physical' ? 'products' : 'services'
    else error.value = apiError(e, 'form.saveError')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="form">
    <h2>{{ form.id ? t('form.edit') : t('form.new') }}</h2>

    <!-- Переключатель вариаций — самое первое, что видно, и дальше форма
         заполняется как обычная: V1 и есть сам товар. «+» добавляет V2 и
         сразу на неё переключает; поля ниже остаются те же самые, меняется
         только то, что у вариаций своё — фото, цена и остаток. -->
    <template v-if="form.type === 'physical'">
      <div class="vrow">
        <button
          v-for="i in Math.max(variants.length, 1)"
          :key="i"
          type="button"
          class="vtab"
          :class="{ active: i - 1 === active }"
          :title="slotTitle(i - 1)"
          @click="active = i - 1"
        >{{ t('form.variantShort', { n: i }) }}</button>
        <button type="button" class="vtab plus" :title="t('form.addVariant')" @click="addVariant">+</button>
      </div>
    </template>

    <!-- Порядок: название -> фото -> тип -> описание -> поля вариации.
         Фото поднято сразу под название и сделано широким: продавец начинает
         с того, что у него уже есть в галерее, а не с выбора типа товара. -->
    <label>{{ t('form.titleLabel') }}</label>
    <input v-model="slot.title" maxlength="256" :placeholder="t('form.titlePh')" />

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
      v-if="!slot.image_url"
      class="drop-zone"
      type="button"
      :disabled="uploadingImage"
      @click="fileInput.click()"
    >
      <span class="drop-icon">+</span>
      <span>{{ uploadingImage ? t('form.uploading') : t('form.pickPhoto') }}</span>
    </button>

    <!-- «Заменить» и «Удалить» лежат поверх самого фото: рядом с ним они не
         помещались по ширине экрана и молча уезжали за правый край -->
    <div v-else class="image-box wide">
      <div
        class="thumb big"
        role="button"
        tabindex="0"
        :aria-label="t('form.photoEdit')"
        @click="photoMenu = !photoMenu"
        @keydown.enter.prevent="photoMenu = !photoMenu"
        @keydown.space.prevent="photoMenu = !photoMenu"
      >
        <span v-if="uploadingImage || imgLoading" class="spinner" />
        <img
          v-show="!uploadingImage && !imgLoading"
          :src="slot.image_url"
          :alt="t('form.photoAlt')"
          @load="imgLoading = false"
          @error="imgLoading = false"
        />
        <!-- значок остаётся видимым всегда: иначе о том, что фото нажимается,
             узнать неоткуда -->
        <span v-if="!photoMenu" class="edit-hint" aria-hidden="true">✏️</span>
        <div v-else class="photo-actions" @click.stop>
          <button class="btn act" type="button" :disabled="uploadingImage" @click="fileInput.click()">
            {{ uploadingImage ? '…' : t('form.replace') }}
          </button>
          <button class="btn act danger" type="button" @click="dropImage">
            {{ t('form.remove') }}
          </button>
        </div>
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
    <textarea v-model="slot.description" rows="3" :placeholder="t('form.descPh')" />

    <!-- Дальше — поля, которые у товара с вариациями свои у каждой. Разметка
         одна на оба случая: пишет она в товар или в вариацию, решает slot. -->
    <template v-if="hasVariants">
      <label>{{ t('form.variantLabelField') }}</label>
      <div class="vname">
        <input v-model="slot.label" maxlength="64" :placeholder="t('form.variantLabelPh')" />
        <button type="button" class="link danger" @click="removeVariant(active)">
          {{ t('form.removeVariant') }}
        </button>
      </div>
      <p class="hint">{{ t('form.variantLabelHint') }}</p>
    </template>

    <label>{{ t('form.priceLabel') }}</label>
    <input v-model="slot.price" inputmode="decimal" placeholder="9.99" />

    <label>{{ t('form.compareLabel') }}</label>
    <input v-model="slot.compare_at_price" inputmode="decimal" placeholder="19.99" />
    <p class="hint">{{ t('form.compareHint') }}</p>

    <template v-if="form.type === 'physical'">
      <label>{{ t('form.stockLabel') }}</label>
      <input v-model="slot.stock" inputmode="numeric" :placeholder="t('form.stockPh')" />
      <p v-if="stockInvalid" class="error">{{ t('form.stockInvalid') }}</p>
    </template>

    <template v-if="form.type !== 'physical'">
      <label>{{ t('form.digitalUrlLabel') }}</label>
      <input v-model="form.digital_url" placeholder="https://…" />
    </template>

    <label class="check">
      <input type="checkbox" v-model="form.is_active" /> {{ t('form.showOnStorefront') }}
    </label>

    <p v-if="error" class="error">{{ error }}</p>

    <PlanModal v-if="planLimit" :reason="planLimit" @close="planLimit = null" @paid="planLimit = null; submit()" />

    <div class="actions">
      <button class="btn btn-soft" @click="router.push(`/shop/${botId}`)">{{ t('common.cancel') }}</button>
      <button
        class="btn btn-primary"
        :disabled="!slot.title || !slot.price || stockInvalid || saving"
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
/* .wide — колонка, а не строка: при строке широкий thumb забирал всю ширину,
   а всё, что стояло рядом, выдавливалось за экран */
.image-box.wide { display: block; position: relative; }
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
/* действия поверх фото: по нажатию на картинку */
.photo-actions {
  position: absolute; inset: 0; border-radius: inherit;
  background: rgba(10, 10, 16, 0.62);
  display: flex; align-items: center; justify-content: center; gap: 10px;
}
.photo-actions .act {
  /* глобальный .btn тянет кнопку на всю ширину — здесь она по содержимому */
  flex: 0 0 auto; width: auto;
  height: 44px; padding: 0 22px; font-size: 15px; font-weight: 700;
  border: 0; border-radius: 12px; cursor: pointer;
  background: #fff; color: #16151c;
}
.photo-actions .act.danger { background: rgba(255, 255, 255, 0.14); color: #fff; }
.photo-actions .act:disabled { opacity: 0.5; }
.edit-hint {
  position: absolute; right: 9px; bottom: 9px;
  width: 30px; height: 30px; border-radius: 50%;
  background: rgba(10, 10, 16, 0.55);
  display: flex; align-items: center; justify-content: center; font-size: 14px;
}
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
.thumb.big { width: 100%; height: 168px; border-radius: 15px; overflow: hidden; cursor: pointer; }
.thumb.big:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.thumb.big img { width: 100%; height: 100%; object-fit: cover; }

/* Переключатель вариаций: мелкие квадратики над всей формой. Он не должен
   выглядеть как ещё один ряд выбора (тип товара, ниже) — там кнопки во всю
   ширину, здесь ровно наоборот: чем меньше, тем понятнее, что это вкладки. */
.vrow { display: flex; flex-wrap: wrap; gap: 7px; margin: 2px 0 4px; }
.vtab {
  width: 42px; height: 38px; flex: 0 0 auto;
  border: 1px solid var(--border); background: var(--surface); color: var(--sub);
  border-radius: 12px; cursor: pointer; font-weight: 800; font-size: 13px;
}
.vtab.active { border-color: var(--accent); background: var(--accent-soft); color: var(--accent); }
.vtab.plus { border-style: dashed; border-color: var(--accent); color: var(--accent); font-size: 18px; }
/* название вариации и «Убрать» — одной строкой: удаление относится именно к
   той вариации, что сейчас открыта, и стоять оно должно рядом с её именем */
.vname { display: flex; align-items: center; gap: 8px; }
.vname input { flex: 1; }
.link { border: 0; background: none; color: var(--accent); font-size: 13px; font-weight: 700; cursor: pointer; padding: 4px 0; white-space: nowrap; }
.link.danger { color: var(--red); }
</style>
