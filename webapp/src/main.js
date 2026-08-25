import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { attachBackButton } from './services/backButton'
import './styles.css'
import router from './router'

attachBackButton(router)

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
