<template>
  <AppLayout />
</template>

<script setup>
import AppLayout from '@/layouts/AppLayout/AppLayout.vue'
import { onMounted, onBeforeMount } from 'vue'

onBeforeMount(() => {
  document.documentElement.setAttribute('theme', localStorage.getItem('theme'))
})

onMounted(() => {
  const tg = window.Telegram.WebApp

  const color = getComputedStyle(document.body).getPropertyValue('--main-bg')

  tg.setHeaderColor(color)
  tg.setBackgroundColor(color)
  tg.setBottomBarColor(color)
})
</script>
