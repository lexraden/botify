<template>
  <footer class="footer">
    <nav class="footer__nav nav">
      <router-link class="nav__link" to="/" :class="{ nav__link_active: homeIsActive }">
        <Icon class="nav__icon" icon="iconoir:home-simple" />
        <span class="nav__text">{{ t('MainPage') }}</span>
      </router-link>

      <router-link class="nav__link" to="/add" :class="{ nav__link_active: createIsActive }">
        <Icon class="nav__icon" icon="lucide:square-plus" />
        <span class="nav__text">{{ t('GuidePage') }}</span>
      </router-link>

      <router-link class="nav__link" to="/earn" :class="{ nav__link_active: profileIsActive }">
        <Icon class="nav__icon" icon="gravity-ui:person" />

        <span class="nav__text">{{ t('EarnPage') }}</span>
      </router-link>
    </nav>
  </footer>
</template>

<script setup>
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

const route = useRoute()

const homeIsActive = computed(() => route.path === '/')
const createIsActive = computed(() => route.path === '/add' || route.path === '/add_form')
const profileIsActive = computed(() => route.path == '/earn')

const { t } = useI18n({ useScope: 'global' })
</script>

<style scoped lang="scss" src="./TheFooter.scss" />
