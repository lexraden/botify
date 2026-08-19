<template>
  <div class="search-page">
    <div class="search-page__results results">
      <div class="results__header">
        <Icon
          icon="fluent:ios-arrow-left-24-filled"
          class="results__back-icon"
          @click="resetView"
        />

        <label class="results__input-field">
          <Icon
            icon="gravity-ui:magnifier"
            @click="toggleSearchInput"
            class="results__search-icon"
          />

          <input
            type="text"
            class="results__input"
            :placeholder="t('mainInputPlaceholder')"
            v-model="searchTerm"
            @input="onSearch"
            @focus="showRecentSearches = true"
            @blur="hideRecentSearches"
          />
        </label>
      </div>
      <!-- Search Results -->
      <div v-if="searchResults.length > 0" class="results__content">
        <h3 class="results__heading">{{ t('SearchResults') }}</h3>
        <GuidesList :items="searchResults" />
      </div>

      <div v-else-if="showInput && (!searchTerm || searchResults.length === 0)">
        <!-- Placeholder if no search results -->
        No results
      </div>
    </div>

    <div
      class="search-page__recent-searches recent-searches"
      v-if="showRecentSearches && recentSearches.length > 0"
    >
      <ul class="recent-searches__list">
        <li
          class="recent-searches__list-item"
          v-for="(search, index) in recentSearches"
          :key="index"
          @mousedown.prevent="selectRecentSearch(search)"
        >
          <Icon class="recent-searches__history-icon" icon="material-symbols:history" />
          <span class="recent-searches__text">{{ search }}</span>
          <img
            src="https://www.trustedreviews.com/wp-content/uploads/sites/54/2021/04/Telegram-920x585.png"
            alt="icon"
            class="recent-searches__image"
          />
          <Icon class="recent-searches__arrow-icon" icon="ph:arrow-up-left-light" />
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Icon } from '@iconify/vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { onMounted, nextTick } from 'vue'

const { t } = useI18n({ useScope: 'global' })
import { searchGuides } from '@/api'
import GuidesList from '@/components/GuidesList/GuidesList.vue'

const searchTerm = ref('')
const searchResults = ref([])
const recentSearches = ref([])
const showRecentSearches = ref(false)
const showInput = ref(false) // Control input visibility
const showSeeMore = ref(false)

const router = useRouter()
const toggleSearchInput = () => {
  showInput.value = !showInput.value
}

const resetView = () => {
  router.go(-1)
  if (router.currentRoute.value.name !== 'Main') {
    router.push({ name: 'Main' })
  }
}
const onSearch = () => {
  if (searchTerm.value.trim() === '') {
    searchResults.value = []
    showRecentSearches.value = true
    return
  }
  handleSearchGuides(searchTerm.value)
}

const handleSearchGuides = async (search) => {
  try {
    const data = await searchGuides(search)

    searchResults.value = data
    addToRecentSearches(search)
    showSeeMore.value = searchResults.value.length > 5
    showRecentSearches.value = false
  } catch (error) {
    console.error('Error searching guides:', error)
  }
}

const loadRecentSearches = () => {
  const storedSearches = JSON.parse(localStorage.getItem('recentSearches') || '[]')
  recentSearches.value = storedSearches
}

const addToRecentSearches = (search) => {
  if (!recentSearches.value.includes(search)) {
    recentSearches.value.unshift(search)
    if (recentSearches.value.length > 10) {
      recentSearches.value.pop()
    }
    localStorage.setItem('recentSearches', JSON.stringify(recentSearches.value))
  }
}

const selectRecentSearch = (search) => {
  searchTerm.value = search
  showRecentSearches.value = false
  handleSearchGuides(search)
}

const hideRecentSearches = () => {
  setTimeout(() => {
    showRecentSearches.value = false
  }, 150)
}

const adjustIconPosition = () => {
  const icon = document.querySelector('.input_block svg')
  if (icon) {
    icon.style.left = '8%'
    icon.style.top = '50%'
    icon.style.transform = 'translateY(-50%)'
  }
}

onMounted(async () => {
  loadRecentSearches()
  await nextTick()
  adjustIconPosition()
})
</script>

<style scoped lang="scss" src="./SearchPage.scss" />
