<template>
  <div class="ru-page">
    <h3 class="ru-page__heading">Русский</h3>
    <GuidesList :items="allTasks" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { loadTasks } from '@/api'

import GuidesList from '@/components/GuidesList/GuidesList.vue'

const emit = defineEmits(['contentLoaded'])

// Переменные для текущего языка и списка задач
// const currentLanguage = ref('RU')
const allTasks = ref([])

// Загружаем задачи на русском по умолчанию при монтировании компонента
onMounted(async () => {
  const data = await loadTasks()

  allTasks.value = data

  emit('contentLoaded')
})
</script>

<style scoped lang="scss" src="./FeaturesRu.scss" />
