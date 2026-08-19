<script setup>
import { onMounted } from 'vue'
import { initTelegram } from './services/telegram'

onMounted(initTelegram)
</script>

<template>
  <router-view />
</template>

<style lang="scss">
body {
  margin: 0;
  font-family: -apple-system, system-ui, sans-serif;
  background: var(--tg-theme-bg-color, #fff);
  color: var(--tg-theme-text-color, #000);
}
* { -webkit-tap-highlight-color: transparent; }
</style>
