<template>
  <div class="guide" @click="openGuide(item.id)">
    <div class="guide__info">
      <img class="guide__image" :src="getGuideImageUrl(item.mainImg)" alt="Guide Image" />
      <p class="guide__title">{{ t('Guide') }}: {{ item.description }}</p>

      <div class="guide__tooltip tooltip">
        <button type="button" class="tooltip__button" @click.stop.prevent="toggleTooltip(item.id)">
          <Icon class="guide__more-icon" icon="pepicons-pencil:dots-x" />
        </button>

        <div v-if="tooltipVisible === item.id" class="tooltip__content">
          <ul class="tooltip__options">
            <li class="tooltip__option" @click.stop="share(item.id)">
              <Icon icon="material-symbols:share-outline" />
              {{ t('Share') }}
            </li>
          </ul>
        </div>
      </div>
    </div>

    <div class="guide__earnings">
      <p class="guide__earnings-text">
        <span>{{ t('EarnedTotal') }}:</span> <TelegramStar size="10" />
        <span>{{ item.earnings }}</span>
      </p>
      <p class="guide__earnings-text">
        <span>{{ t('EarnedPerWeek') }}:</span> <TelegramStar size="10" />
        <span>{{ item.weeklyEarnings }}</span>
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { getGuideImageUrl } from '@/api'
import { Icon } from '@iconify/vue'
import { useI18n } from 'vue-i18n'

import TelegramStar from '@/components/ui/icons/TelegramStar.vue'

defineProps(['item'])

const tooltipVisible = ref(null)

function toggleTooltip(id) {
  tooltipVisible.value = tooltipVisible.value === id ? null : id
}

function share(id) {
  console.log(`Share clicked for item ${id}`)
}

function handleClickOutside(event) {
  const tooltipElement = document.querySelector('.tooltip')
  const buttonElement = document.querySelector('.tooltip__button')

  if (
    tooltipVisible.value &&
    !tooltipElement.contains(event.target) &&
    !buttonElement.contains(event.target)
  ) {
    tooltipVisible.value = null
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
const { t } = useI18n({ useScope: 'global' })

const router = useRouter()

function openGuide(guideId) {
  router.push(`/guide/${guideId}`)
}
</script>

<style scoped lang="scss" src="./MyGuideItem.scss" />
