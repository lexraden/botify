<script setup>
// Единственная реклама платформы в витрине: покупатель видит её в каждом
// магазине, клик ведёт на наш бот
const BOTIFY_URL = 'https://t.me/Botifyapp_bot'
</script>

<template>
  <a class="made-with" :href="BOTIFY_URL" target="_blank" rel="noopener">
    Сделано через <b>Botify</b>
  </a>
</template>

<style scoped>
.made-with {
  display: block;
  width: max-content;
  margin: 28px auto 0;
  padding: 7px 14px;
  border-radius: 999px;
  background: var(--surface2);
  font-size: 12px;
  color: var(--sub);
  text-decoration: none;
}
.made-with b { color: var(--text); font-weight: 700; }
</style>
