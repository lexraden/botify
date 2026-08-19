<template>
  <button type="button" @click="$router.push(`/guide/${item.id}`)" class="item" :key="item.id">
    <img :src="getGuideImageUrl(item.mainImg)" alt="" class="item__image" />

    <div class="item__text">
      <div class="item__heading">
        {{ item.name }}
      </div>

      <a @click.prevent.stop="$router.push(`/profile/${item.author}`)" class="item__author-name">
        @{{ item.author }}
      </a>

      <div class="item__info">
        <p class="item__date">
          {{ formatTimeAgo(item.createdAt) }}
        </p>

        <div class="item__price-block">
          <span class="item__star-icon"><TelegramStar size="17" /></span>
          <span class="item__price">{{ item.price }}</span>
        </div>
      </div>
    </div>

    <div class="item__tooltip tooltip">
      <button type="button" class="tooltip__button" @click.stop.prevent="toggleTooltip(item.id)">
        <Icon class="tooltip__icon" icon="mage:dots" />
      </button>

      <div v-if="tooltipVisible === item.id" class="tooltip__content">
        <ul class="tooltip__options">
          <li class="tooltip__option" @click.stop="share(item.id)">
            <Icon icon="material-symbols:share-outline" />
            {{ t('Share') }}
          </li>
          <li v-if="isOwnGuide" class="tooltip__option" @click.stop="edit(item.id)">
            <Icon icon="lucide:edit" />
            {{ t('Edit') }}
          </li>
          <li v-if="isOwnGuide" class="tooltip__option" @click.stop="deleteItem(item.id)">
            <Icon icon="fluent-mdl2:delete" />
            {{ t('Delete') }}
          </li>
        </ul>
      </div>
    </div>
  </button>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Icon } from '@iconify/vue'

import { formatTimeAgo } from '@/utils/format'
import { getGuideImageUrl } from '@/api'
import TelegramStar from '@/components/ui/icons/TelegramStar.vue'
import { useUserStore } from '@/store/userStore'

const userStore = useUserStore()

const { t } = useI18n({ useScope: 'global' })
const props = defineProps(['item'])

const tooltipVisible = ref(null)

function toggleTooltip(id) {
  tooltipVisible.value = tooltipVisible.value === id ? null : id
}

function share(id) {
  console.log(`Share clicked for item ${id}`)
}

function edit(id) {
  console.log(`Edit clicked for item ${id}`)
}

function deleteItem(id) {
  console.log(`Delete clicked for item ${id}`)
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

const isOwnGuide = computed(() => userStore.username === props.item.author)

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<style scoped lang="scss" src="./GuidesListItem.scss" />
