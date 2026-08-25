import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { attachBackButton } from './services/backButton'
import { applyTheme } from './services/theme'
import './styles.css'
import router from './router'

// тема до первого рендера, чтобы не мигнуть светлым в тёмном клиенте
applyTheme()
attachBackButton(router)

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
