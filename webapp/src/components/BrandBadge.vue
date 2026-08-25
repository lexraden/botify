<script setup>
// Единственная реклама платформы в витрине: покупатель видит её в каждом
// магазине, клик ведёт на наш бот. Прибита к низу экрана (с safe-area);
// страницы, где она показана, обязаны держать снизу свободное место — иначе
// плашка ляжет поверх контента. Слой ниже фиксированных панелей (корзина,
// кнопка оплаты): они перекрывают плашку, а не наоборот.
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
  position: fixed;
  left: 0;
  right: 0;
  bottom: calc(10px + env(safe-area-inset-bottom));
  z-index: 1;
  width: max-content;
  margin: 0 auto;
  font-size: 12px;
  color: var(--sub);
  text-decoration: none;
}
.made-with b { color: var(--sub); font-weight: 700; }
</style>
