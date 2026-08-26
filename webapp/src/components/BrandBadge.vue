<script setup>
// Единственная реклама платформы в витрине: покупатель видит её в каждом
// магазине, клик ведёт на наш бот. Плашка живёт в обычном потоке страницы —
// просто последним элементом контента и скроллится вместе с ним; ставить её
// нужно последним ребёнком вью, где она уместна.
import { t } from '../i18n'

const BOTIFY_URL = 'https://t.me/Botifyapp_bot'
</script>

<template>
  <a class="made-with" :href="BOTIFY_URL" target="_blank" rel="noopener">
    {{ t('badge.madeWith') }} <b>Botify</b>
  </a>
</template>

<style scoped>
.made-with {
  display: block;
  width: max-content;
  margin: 18px auto 0;
  font-size: 12px;
  color: var(--sub);
  text-decoration: none;
}
.made-with b { color: var(--sub); font-weight: 700; }
</style>
