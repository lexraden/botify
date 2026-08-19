<template>
  <div class="container">
    <router-view class="container__router-view"></router-view>
    <TheFooter class="container__footer"></TheFooter>
  </div>
</template>

<script setup>
import TheFooter from '@/components/TheFooter/TheFooter.vue'
</script>

<style lang="scss" src="./AppLayout.scss" />
