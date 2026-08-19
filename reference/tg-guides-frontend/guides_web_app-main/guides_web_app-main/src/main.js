import '@/assets/style/index.scss'

import { createApp } from 'vue'
import App from './App.vue'
import router from './router'

import { createPinia } from 'pinia'
import axios from 'axios'
import VueAxios from 'vue-axios'

import { createI18n, useI18n } from 'vue-i18n'
import { languages } from './i18n'

const messages = Object.assign(languages)

const pinia = createPinia()

const i18n = createI18n({
  legacy: false,
  fallbackLocale: 'ru',
  locale: localStorage.getItem('lang') == 'English' ? 'en' : 'ru',
  messages
})

createApp(App, {
  setup() {
    const { t } = useI18n
    return { t }
  }
})
  .use(pinia)
  .use(VueAxios, axios)
  .use(router)
  .use(i18n)
  .mount('#app')
