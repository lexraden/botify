<template>
  <div class="my-guides-page">
    <h3 class="my-guides-page__heading">{{ t('MyGuides') }}</h3>

    <div class="my-guides-page__switch-block switch-block">
      <button
        type="button"
        class="switch-block__button"
        @click="loadGuides(false)"
        :class="{ 'switch-block__button_active': changeMenu == 'Bought' }"
      >
        {{ t('Bought') }}
      </button>

      <button
        type="button"
        class="switch-block__button"
        @click="loadGuides(true)"
        :class="{ 'switch-block__button_active': changeMenu == 'Mine' }"
      >
        {{ t('Mine') }}
      </button>
    </div>

    <div class="my-guides-page__guides-list">
      <GuidesList v-if="changeMenu === 'Bought'" :items="visibleBoughtItems" />
      <GuidesList v-else :items="visibleItems" />
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import GuidesList from '@/components/GuidesList/GuidesList.vue'
import { loadUserTasks } from '@/api'

const { t } = useI18n({ useScope: 'global' })

const emit = defineEmits(['contentLoaded'])

const changeMenu = ref('Bought')
const listItems = ref([])
const listBoughtItems = ref([])
const visibleItems = ref([])
const visibleBoughtItems = ref([])

async function loadGuides(own) {
  const tgWebApp = window.Telegram.WebApp
  if (!tgWebApp) {
    console.error(
      'Telegram WebApp не инициализирован. Убедитесь, что запускаете MiniApp в Telegram.'
    )
    return
  }

  const tgUnsafeData = tgWebApp.initDataUnsafe
  changeMenu.value = own ? 'Mine' : 'Bought'

  const data = await loadUserTasks(own)

  try {
    if (own) {
      listItems.value = data.map((guide) => ({
        id: guide.id,
        name: guide.name,
        description: guide.description,
        mainImg: guide.mainImg,
        author: tgUnsafeData.user.username || 'Unknown',
        createdAt: guide.createdAt,
        price: guide.price
      }))
      visibleItems.value = listItems.value.slice(0, 4)
    } else {
      listBoughtItems.value = data.map((guide) => ({
        id: guide.id,
        name: guide.name,
        description: guide.description,
        mainImg: guide.mainImg,
        author: guide.author || 'Unknown',
        createdAt: guide.createdAt,
        price: guide.price
      }))
      visibleBoughtItems.value = listBoughtItems.value.slice(0, 4)
    }
  } catch (error) {
    console.error('Ошибка при загрузке гайдов:', error)
  }
}

// Загрузка купленных гайдов при монтировании
onMounted(async () => {
  const data = await loadUserTasks(false)

  listItems.value = data

  emit('contentLoaded')
})
</script>

<style scoped lang="scss" src="./MineGuides.scss" />
