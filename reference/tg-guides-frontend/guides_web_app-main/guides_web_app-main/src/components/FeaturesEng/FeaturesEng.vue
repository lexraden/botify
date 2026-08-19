<template>
  <div class="eng-page">
    <h3 class="eng-page__heading">English</h3>
    <GuidesList :items="allTasks" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { loadTasks } from '@/api'
import GuidesList from '@/components/GuidesList/GuidesList.vue'

// Переменные для текущего языка и списка задач
// const currentLanguage = ref('ENG')
const allTasks = ref([])

const emit = defineEmits(['contentLoaded'])

// Загружаем задачи на английском языке по умолчанию при монтировании компонента
onMounted(async () => {
  const data = await loadTasks()

  allTasks.value = data

  emit('contentLoaded')
})
</script>

<style scoped lang="scss" src="./FeaturesEng.scss" />
