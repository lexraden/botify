<template>
  <div class="page">
    <header class="page__header header">
      <div class="header__container">
        <nav v-if="!searchTerm" class="header__categories">
          <button
            v-for="(category, index) in categories"
            :key="index"
            class="header__categories-button"
            :class="{ 'header__categories-button_active': activeCategory === index }"
            @click="scrollToTopic(index)"
          >
            {{ category.title }}
          </button>
        </nav>

        <button class="header__search-button" type="button" @click="goToSearch">
          <Icon class="header__search-icon" icon="gravity-ui:magnifier" />
        </button>
      </div>
    </header>

    <main class="main">
      <SearchResult
        v-if="searchTerm && searchResults.length > 0"
        :results="searchResults"
        @select="selectSearchResult"
      />

      <div v-if="isUserAuthenticated" ref="container" class="main__container">
        <section
          class="main__section"
          v-for="(category, index) in categories"
          :key="index"
          :ref="(el) => (categoryRefs[index] = el)"
        >
          <component @content-loaded="handleContentLoaded" :is="category.component" />
        </section>
      </div>
    </main>
  </div>
</template>

<script setup>
import { Icon } from '@iconify/vue'
import { onMounted, ref, onBeforeUnmount, markRaw } from 'vue'
import MineGuides from '@/components/MineGuides/MineGuides.vue'
import TopGuides from '@/components/TopGuides/TopGuides.vue'
import FeaturedEng from '@/components/FeaturesEng/FeaturesEng.vue'
import FeaturedRu from '@/components/FeaturesRu/FeaturesRu.vue'
import SearchResult from '@/components/SearchResult/SearchResult.vue'
import { useI18n } from 'vue-i18n'
import { setUser } from '@/services/telegram'

const { t } = useI18n({ useScope: 'global' })
import { useRouter } from 'vue-router'
const searchTerm = ref('')
const searchResults = ref([])
const activeCategory = ref(0)
const categoryRefs = ref([])
const observers = []

const container = ref()

const isUserAuthenticated = ref(false)

const categories = ref([
  { title: t('AllGuides'), name: 'All Guides', component: markRaw(TopGuides) },
  { title: t('MyGuides'), name: 'My GPTs', component: markRaw(MineGuides) },
  { title: 'English', name: 'FeaturedEng', component: markRaw(FeaturedEng) },
  { title: 'Русский', name: 'FeaturedRu', component: markRaw(FeaturedRu) }
])

const loadedSections = ref(0)
const totalSections = categories.value.length

const handleContentLoaded = () => {
  loadedSections.value++

  if (loadedSections.value === totalSections) {
    window.addEventListener('scroll', handleScroll)
  }
}

function handleScroll() {
  categoryRefs.value.forEach((ref, index) => {
    if (!ref) return

    const rect = ref.getBoundingClientRect()
    if (rect.bottom >= 0 && rect.bottom <= window.innerHeight) {
      activeCategory.value = index
    }
  })
}

const scrollToTopic = (index) => {
  if (!categoryRefs.value[index]) return
  categoryRefs.value[index].scrollIntoView({
    behavior: 'smooth'
  })
}

const router = useRouter()

const goToSearch = () => {
  router.push({ name: 'SearchPage' })
}

// Использование хранилища Pinia
window.Telegram.WebApp.ready()

// Подписка на событие ready
window.Telegram.WebApp.onEvent('ready', () => {
  console.log('Мини-приложение готово к работе')
})

onMounted(async () => {
  await setUser()

  isUserAuthenticated.value = true
})

onBeforeUnmount(() => {
  observers.forEach((observer) => observer.disconnect())
})
</script>

<style scoped lang="scss" src="./MainPage.scss" />
