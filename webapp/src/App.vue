<script setup>
import { onMounted } from 'vue'
import { initTelegram } from './services/telegram'

// Этап 4: сюда переносится витрина из reference/tg-guides-frontend
// (GuidesList -> ProductGrid, MineGuides -> Мои покупки и т.д.)
onMounted(initTelegram)
</script>

<template>
  <main class="placeholder">
    <h1>Botify</h1>
    <p>Витрина в разработке — этап 4 плана (docs/AUDIT.md).</p>
  </main>
</template>

<style lang="scss">
body {
  margin: 0;
  font-family: -apple-system, system-ui, sans-serif;
  background: var(--tg-theme-bg-color, #fff);
  color: var(--tg-theme-text-color, #000);
}
.placeholder {
  padding: 24px;
  text-align: center;
}
</style>
