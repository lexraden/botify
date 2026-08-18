<template>
  <div class="guides-list">
    <div class="guides-list__message" v-if="items && items.length === 0">Гайдов нет</div>

    <GuidesListItem v-for="item in shownItems" :key="item.id" :item="item" />

    <button
      v-if="showMoreButtonVisible"
      type="button"
      @click="toggleShowMore"
      class="guides-list__show-more-button"
    >
      {{ t('SeeMore') }}
      <Icon class="guides-list__show-more-button-icon" icon="solar:alt-arrow-down-line-duotone" />
    </button>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { Icon } from '@iconify/vue'

import GuidesListItem from '@/components/GuidesListItem/GuidesListItem.vue'

const { t } = useI18n({ useScope: 'global' })
const props = defineProps(['items'])

const itemsToShowInitially = 4
const showMore = ref(false)

const shownItems = computed(() => {
  if (!props.items) {
    return []
  }
  return showMore.value ? props.items : props.items.slice(0, itemsToShowInitially)
})

const showMoreButtonVisible = computed(() => {
  return !showMore.value && props.items && props.items.length > itemsToShowInitially
})

function toggleShowMore() {
  showMore.value = true
}

const tooltipVisible = ref(null)
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
</script>

<style scoped lang="scss" src="./GuidesList.scss" />
