<template>
  <div class="guide-creation-page" @click="changeBlur($event)">
    <div v-if="isLoading" class="guide-creation-page__loading-overlay">
      <div class="guide-creation-page__loading-spinner"></div>
      <p>{{ t('Loading') }}...</p>
    </div>

    <form
      class="guide-creation-page__form form"
      v-if="currCon === 'MainPage'"
      @submit.prevent="goToNextPart"
    >
      <div class="form__header">
        <h2 class="form__heading heading">{{ t('GuideCreating') }}</h2>
        <Icon class="form__header-icon" icon="mdi:tick" />
      </div>

      <div class="form__block">
        <div
          class="form__image-field image-field"
          ref="imageInput"
          @click="image.click()"
          :style="{ backgroundImage: url ? 'url(' + url + ')' : 'none' }"
        >
          <input
            type="file"
            class="image-field__input"
            @input="onFileChange"
            id="image_input"
            ref="image"
            hidden
          />

          <div class="image-field__icon-container">
            <Icon class="image-field__plus-icon" icon="octicon:feed-plus-16" v-if="!url" />
            <Icon class="image-field__image-icon" icon="mynaui:image" v-if="!url" />

            <button
              v-if="url"
              type="button"
              class="image-field__delete-button"
              @click.stop="removeImage"
            >
              <Icon icon="pepicons-pop:trash" class="image-field__delete-icon" />
            </button>
          </div>
        </div>

        <label class="form__name-field name-field">
          <input
            class="name-field__input"
            type="text"
            aria-label="name"
            :placeholder="t('GuideName')"
            maxlength="30"
            v-model="guide.name"
            required
          />
          <span class="name-field__word-count">{{ guide.name.length }}/30</span>
        </label>
      </div>

      <div class="form__description-field description-field">
        <div class="description-field__info">
          <p class="description-field__text">{{ t('GuideDescription') }}</p>

          <span class="description-field__word-count">{{ guide.description.length }}/40</span>
        </div>

        <textarea
          class="description-field__input"
          maxlength="40"
          v-model="guide.description"
          required
        />
      </div>

      <div
        class="general-info-form__error-message"
        :class="{ 'general-info-form__error-message_active': errorMessage }"
      >
        {{ errorMessage }}
      </div>

      <button
        class="general-info-form__submit-button submit-button"
        type="submit"
        :disabled="isLoading"
      >
        {{ t('Next') }}
      </button>
    </form>

    <!-- Part 2: Price and Category -->
    <form
      class="guide-creation-page__general-info-form general-info-form"
      v-if="currCon === 'PartTwo'"
      @submit.prevent="saveGuideTempData"
    >
      <div class="general-info-form__header">
        <h2 class="general-info-form__heading heading">{{ t('GuideCreating') }}</h2>
        <Icon class="general-info-form__header-icon" icon="mdi:tick" />
      </div>

      <div class="general-info-form__price-field price-field">
        <p class="price-field__text">{{ t('GuidePrice') }}</p>

        <div class="price-field__block">
          <input
            aria-label="price"
            class="price-field__input"
            type="text"
            v-model="guide.price"
            required
          />
          <span class="general-info-form__star-icon"><TelegramStar size="19" /></span>
        </div>
      </div>

      <div class="general-info-form__categories-field categories-field">
        <p class="categories-field__text">
          {{ t('GuideCategories') }}
        </p>

        <div class="categories-field__categories">
          <div class="categories-field__block">
            <select v-model="currCategory" @change="addCategory" class="categories-field__select">
              <option disabled value="">{{ t('GuideCategories') }}</option>
              <option v-for="category in availableCategories" :key="category" :value="category">
                {{ category }}
              </option>
            </select>

            <Icon class="categories-field__arrow-icon" icon="ri:arrow-down-s-line" />
          </div>

          <p class="categories-field__list">
            <span v-for="category in guide.categories" :key="category">{{ category }}</span>
          </p>
        </div>

        <button
          class="general-info-form__submit-button submit-button"
          type="submit"
          :disabled="isLoading"
        >
          {{ t('Next') }}
        </button>
      </div>
    </form>

    <form class="chapter-form" v-if="currCon === 'ChapterPage'" @submit.prevent="addChapter">
      <div class="chapter-form__heading heading">
        {{ t('Chapter') }} {{ guide.chaptersList.length + 1 }}
      </div>

      <div class="chapter-form__name-field">
        <p class="chapter-form__name-text">
          <span>{{ t('ChapterName') }}</span>
          <span>{{ chapter.name ? chapter.name.length : 0 }}/20</span>
        </p>

        <input
          class="chapter-form__name-input"
          type="text"
          v-model="chapter.name"
          maxlength="20"
          required
        />
      </div>

      <div class="chapter-form__video-field">
        <p class="chapter-form__video-text">{{ t('ChapterVideo') }}</p>
        <div
          class="chapter-form__video-input"
          ref="videoInputBlock"
          @click="$refs.inputVideo.click()"
        >
          <div class="chapter-form__video-prompt" v-if="!chapter.video">
            <span>{{ t('ChapterVideoText') }}</span>
            <Icon class="chapter-form__download-icon" icon="solar:download-outline" />
          </div>
          <div class="chapter-form__video-prompt" v-else>{{ chapter.video.name }}</div>
        </div>

        <input type="file" ref="inputVideo" id="inputVideo" @input="setInputVideo" hidden />
      </div>

      <div class="chapter-form__photo-field">
        <p class="chapter-form__photo-text">{{ t('ChapterPhoto') }}</p>

        <div
          class="chapter-form__photo-input"
          ref="photoInputBlock"
          @click="$refs.inputPhoto.click()"
        >
          <div class="chapter-form__photo-prompt" v-if="!chapter.image">
            <span>{{ t('ChapterPhotoText') }}</span>
            <Icon class="chapter-form__download-icon" icon="solar:download-outline" />
          </div>

          <div class="chapter-form__photo-prompt" v-else>{{ chapter.image.name }}</div>
        </div>

        <input type="file" ref="inputPhoto" id="inputPhoto" @input="setInputImage" hidden />
      </div>

      <div class="chapter-form__description-field">
        <p class="chapter-form__description-text">
          {{ t('ChapterDescription') }}<span> {{ chapter.description.length }}/80</span>
        </p>

        <textarea
          class="chapter-form__description-input"
          type="text"
          maxlength="80"
          v-model="chapter.description"
          required
        />
      </div>

      <div class="chapter-form__buttons">
        <div class="chapter-form__navigation-buttons">
          <button
            class="chapter-form__navigation-button"
            type="button"
            @click="goToPreviousChapter"
          >
            {{ t('Back') }}
          </button>

          <button
            class="chapter-form__navigation-button"
            type="button"
            @click="goToNextChapter"
            :disabled="isLoading"
          >
            {{ t('Next') }}
          </button>
        </div>

        <button
          type="button"
          class="chapter-form__submit-button submit-button"
          @click="submitGuide"
          :disabled="isLoading"
        >
          {{ t('End') }}
        </button>
      </div>
    </form>
  </div>
</template>

<script setup>
import { Icon } from '@iconify/vue'
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { createGuide } from '@/api'
import TelegramStar from '@/components/ui/icons/TelegramStar.vue'

const { t } = useI18n({ useScope: 'global' })

// Переменная для отслеживания состояния загрузки
let isLoading = ref(false)

const guide = ref({
  name: '',
  author: window.Telegram.WebApp.initDataUnsafe.user?.id,
  image: null,
  description: '',
  price: null,
  categories: [],
  chaptersList: []
})

let chapter = ref({ name: '', video: null, image: null, description: '' })
let currCategory = ref('')
let image = ref(null)
let url = ref('')
let currCon = ref('MainPage')
const errorMessage = ref('')

function goToNextPart() {
  if (url.value) {
    errorMessage.value = ''
    currCon.value = 'PartTwo'
  } else {
    errorMessage.value = 'Требуется загрузить фотографию'
  }
}

function goToPreviousChapter() {
  if (guide.value.chaptersList.length > 0) {
    const previousChapter = guide.value.chaptersList.pop()
    chapter.value = {
      name: previousChapter.name || '',
      video: previousChapter.video || null,
      image: previousChapter.image || null,
      description: previousChapter.description || ''
    }
  }
}

function goToNextChapter() {
  addChapter()

  chapter.value = {
    name: '',
    video: null,
    image: null,
    description: ''
  }
}

function saveGuideTempData() {
  currCon.value = 'ChapterPage'
}

function onFileChange(event) {
  const file = event.target.files[0]
  if (file) {
    const uniqueFileName = generateUniqueFileName(file.name)
    guide.value.image = { file, uniqueFileName }
    url.value = URL.createObjectURL(file)
  }
}

function removeImage() {
  guide.value.image = null
  url.value = ''
}

const availableCategories = ref(['Категория 1', 'Категория 2', 'Категория 3', 'Категория 4']) // Ваш список категорий

function addCategory() {
  if (currCategory.value && guide.value.categories.length < 3) {
    if (!guide.value.categories.includes(currCategory.value)) {
      guide.value.categories.push(currCategory.value)
      currCategory.value = ''
    }
  }
}

function addChapter() {
  const uniqueImageName = chapter.value.image
    ? generateUniqueFileName(chapter.value.image.name)
    : ''
  const uniqueVideoName = chapter.value.video
    ? generateUniqueFileName(chapter.value.video.name)
    : ''

  guide.value.chaptersList.push({
    name: chapter.value.name,
    description: chapter.value.description,
    image: chapter.value.image
      ? { file: chapter.value.image, uniqueFileName: uniqueImageName }
      : null,
    video: chapter.value.video
      ? { file: chapter.value.video, uniqueFileName: uniqueVideoName }
      : null
  })
  chapter.value = { name: '', video: null, image: null, description: '' }
}

function setInputImage(event) {
  const file = event.target.files[0]
  if (file) {
    chapter.value.image = file
  }
}

function setInputVideo(event) {
  const file = event.target.files[0]
  if (file) {
    chapter.value.video = file
  }
}

function changeBlur(e) {
  if (!e.target.localName === 'textarea' || !e.target.localName === 'input') {
    document.activeElement.blur()
  }
}

function generateUniqueFileName(fileName) {
  const timestamp = Date.now()
  const fileExtension = fileName.split('.').pop()
  return `${fileName.split('.')[0]}_${timestamp}.${fileExtension}`
}

async function submitGuide() {
  // Включаем индикатор загрузки
  isLoading.value = true

  const formData = new FormData()

  // Добавляем основную информацию о гайде
  formData.append(
    'guideData',
    JSON.stringify({
      name: guide.value.name,
      description: guide.value.description,
      price: guide.value.price,
      author: guide.value.author,
      language: 'RU'
    })
  )

  // Добавляем изображение гайда, если оно есть
  if (guide.value.image) {
    formData.append('mainImg', guide.value.image.file, guide.value.image.uniqueFileName)
  }

  // Сериализация всех глав в один JSON-объект
  const chaptersData = guide.value.chaptersList.map((chapter) => ({
    name: chapter.name,
    text: chapter.description
  }))

  // Добавляем главы как строку JSON в формате, ожидаемом на сервере
  formData.append('chapters', JSON.stringify(chaptersData))

  // Добавляем файлы глав, если они есть
  guide.value.chaptersList.forEach((chapter) => {
    if (chapter.image) {
      formData.append(`chapterImages`, chapter.image.file, chapter.image.uniqueFileName)
    }
    if (chapter.video) {
      formData.append(`chapterVideos`, chapter.video.file, chapter.video.uniqueFileName)
    }
  })

  // Отправка данных гайда и глав на сервер

  try {
    const response = await createGuide(formData)

    isLoading.value = false

    // Получаем ID гайда из ответа
    const guideId = response.data
    console.log('Гайд успешно создан с ID:', guideId)

    // Перенаправляем пользователя на страницу гайда
    window.location.href = `/guide/${guideId}`
  } catch (error) {
    isLoading.value = false
    console.error('Ошибка при создании гайда:', error)
  }
}
</script>

<style scoped lang="scss" src="./AddFormPage.scss" />
