<template>
  <div class="guide-page">
    <img class="guide-page__image-cover" :src="currentGuide.mainImg" alt="" />

    <h2 class="guide-page__heading">
      {{ currentGuide.name }}
    </h2>

    <div class="guide-page__content content">
      <p
        class="content__categories"
        v-if="currentGuide.categories && currentGuide.categories.length"
      >
        {{ t('GuideCategories') }}: {{ currentGuide.categories.join(' / ') }}
      </p>

      <p class="content__description">
        {{ t('GuideDescription') }}: {{ currentGuide.description }}
      </p>

      <p class="content__author">{{ t('GuideAuthor') }}: @{{ currentGuide.author }}</p>

      <div
        class="content__info-list"
        v-if="currentGuide.chapters && currentGuide.chapters.length > 0"
      >
        <button
          type="button"
          class="content__info-item"
          v-for="(item, index) in currentGuide.chapters"
          @click="scrollToChapter(index)"
          :key="item.id"
        >
          <p class="content__info-name">
            <span>{{ t('Chapter') }} {{ index + 1 }}: {{ item.name }}</span>

            <Icon
              class="content__info-arrow-icon"
              icon="solar:alt-arrow-right-line-duotone"
              :class="{ 'content__info-arrow-icon_active': currChap.includes(item.id) }"
            />
          </p>
        </button>
      </div>

      <div class="content__buy-section">
        <button
          v-if="currentGuide.chapters && currentGuide.chapters.length === 0"
          type="button"
          class="content__buy-button"
          @click="handleBuyGuide"
        >
          <span>{{ t('BuyGuide') }}</span>
          <TelegramStar size="17" />
          <span>{{ currentGuide.price }}</span>
        </button>

        <button type="button" class="content__share-button">
          <Icon icon="solar:share-outline" class="content__share-icon" />
          {{ t('Share') }}
        </button>
      </div>

      <div class="content__chapter-list chapter-list">
        <div
          class="chapter-list__item"
          v-for="(item, index) in currentGuide.chapters"
          :key="item.id"
          :ref="(el) => (chapterRefs[index] = el)"
        >
          <h3 class="chapter-list__title">
            <span>{{ t('Chapter') }} {{ index + 1 }}:</span>
            <span>{{ item.name }}</span>
          </h3>

          <img v-if="item.img" :src="item.img" alt="Chapter Image" class="chapter-list__image" />

          <p class="chapter__list-text">{{ item.text }}</p>

          <video class="chapter__list-video" v-if="item.video" controls>
            <source :src="item.video" type="video/mp4" />
          </video>
        </div>
      </div>

      <button
        v-if="currentGuide.chapters && currentGuide.chapters.length > 0"
        type="button"
        class="content__button-up"
        @click="scroll"
      >
        <Icon class="content__icon-up" icon="solar:alt-arrow-up-line-duotone" />
        <p>{{ t('Up') }}</p>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'

import { useI18n } from 'vue-i18n'
import { Icon } from '@iconify/vue'
const { t } = useI18n()
import { buyGuide, fetchGuide } from '@/api'
import TelegramStar from '@/components/ui/icons/TelegramStar.vue'

const personId = ref(null)
const currChap = ref([])
const currentGuide = ref({
  name: '',
  mainImg: '',
  description: '',
  author: '',
  categories: [],
  chapters: []
})
const chapterRefs = ref([])

const scrollToChapter = (index) => {
  chapterRefs.value[index].scrollIntoView({
    behavior: 'smooth'
  })
}

const initializeTelegram = () => {
  const tg = window.Telegram.WebApp
  tg.ready()

  // Получаем user ID из Telegram Web App и сохраняем в personId
  if (tg.initDataUnsafe && tg.initDataUnsafe.user) {
    personId.value = tg.initDataUnsafe.user.id
  }
}
// Получаем ID гайда из URL
const route = useRoute()
const guideId = route.params.id

const handleBuyGuide = async () => {
  try {
    if (!guideId || !personId.value) {
      alert('Missing guideId or personId')
      return
    }

    const data = await buyGuide(guideId, personId.value)

    console.log('Purchase successful:', data)
    alert(t('PayInBot'))
  } catch (error) {
    alert(error.response?.data?.message || 'An error occurred during the purchase.')
  }
}

onMounted(async () => {
  initializeTelegram()

  const data = await fetchGuide(route.params.id)
  currentGuide.value = data
})

const scroll = () => {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}
</script>

<style scoped lang="scss" src="./GuidePage.scss" />
