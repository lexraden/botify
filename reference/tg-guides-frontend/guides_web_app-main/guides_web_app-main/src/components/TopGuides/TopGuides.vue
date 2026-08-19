<template>
  <div class="featured-page">
    <h3 class="featured-page__heading">{{ t('Main') }}</h3>
    <GuidesList :items="allTasks" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { loadTasks } from '@/api'

import GuidesList from '@/components/GuidesList/GuidesList.vue'

const emit = defineEmits(['contentLoaded'])

const { t } = useI18n({ useScope: 'global' })
const allTasks = ref([])

onMounted(async () => {
  const data = await loadTasks()

  allTasks.value = data

  emit('contentLoaded')
})
</script>

<style scoped lang="scss" src="./TopGuides.scss" />
