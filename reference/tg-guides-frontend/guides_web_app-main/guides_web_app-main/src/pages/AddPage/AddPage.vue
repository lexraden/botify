<template>
  <div class="guide-creation">
    <img class="guide-creation__image" src="@/assets/img/book.png" alt="book" />

    <div class="guide-creation__text">
      <h2 class="guide-creation__heading">{{ t('CreateGuide') }}</h2>

      <p class="guide-creation__paragraph">
        Lorem ipsum, dolor sit amet consectetur adipisicing elit. Placeat odio ut beatae assumenda
        fugiat tempore in amet repellendus nihil veniam? Quam voluptatum eligendi magni nulla
        excepturi eum, saepe repellat laudantium.
      </p>
    </div>

    <router-link class="guide-creation__link" to="/add_form">
      <Icon class="guide-creation__link-icon" icon="lucide:square-plus" />
      {{ t('CreateGuide') }}
    </router-link>
  </div>
</template>

<script setup>
import { Icon } from '@iconify/vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n({ useScope: 'global' })
</script>

<style scoped lang="scss" src="./AddPage.scss" />
