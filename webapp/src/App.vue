<script setup>
import { onMounted } from 'vue'
import { initTelegram } from './services/telegram'

onMounted(initTelegram)
</script>

<template>
  <router-view />
</template>
