<template>
  <div class="featured_content">
    <div v-if="results.length > 0">
      <h3>{{ t('SearchResults') }}</h3>
      <div class="list_items">
        <div v-for="guide in results" :key="guide.id" class="curr_item">
          <img :src="getGuideImageUrl(guide.mainImg)" alt="Guide Image" />
          <div class="item_text">
            <h4 class="text_header" :style="{ whiteSpace: 'normal', overflow: 'visible' }">
              {{ guide.name }}
            </h4>
            <p class="text_content" :style="{ whiteSpace: 'normal', overflow: 'visible' }">
              {{ guide.description }}
            </p>
            <a :href="`/guide/${guide.id}`">{{ t('ReadMore') }}</a>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import { getGuideImageUrl } from '@/api'

const { t } = useI18n({ useScope: 'global' })
</script>

<style scoped lang="scss" src="./SearchResult.scss" />
