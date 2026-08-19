<script setup>
import { onMounted } from 'vue'
import { initTelegram } from './services/telegram'
import LoadingOverlay from './components/LoadingOverlay.vue'

onMounted(initTelegram)
</script>

<template>
  <router-view />
  <LoadingOverlay />
</template>
