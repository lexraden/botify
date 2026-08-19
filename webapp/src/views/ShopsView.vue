<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { fetchMe } from '../api'

const router = useRouter()
const bots = ref(null)

onMounted(async () => {
  const me = await fetchMe()
  bots.value = me.bots
})
</script>

<template>
  <div class="shops">
    <h2>Мои магазины</h2>
    <p class="lead">Каждый бот — отдельный магазин со своим каталогом и базой покупателей.</p>

    <div v-for="bot in bots" :key="bot.id" class="card shop" @click="router.push(`/shop/${bot.id}`)">
      <div class="avatar">{{ bot.bot_username.charAt(0).toUpperCase() }}</div>
      <div class="info">
        <b>@{{ bot.bot_username }}</b>
        <span :class="bot.is_active ? 'on' : 'off'">
          {{ bot.is_active ? 'работает' : 'отключён' }}
        </span>
      </div>
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--sub)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M9 6l6 6-6 6" />
      </svg>
    </div>

    <button class="btn add" @click="router.push('/onboarding/bot')">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round">
        <path d="M12 5v14" /><path d="M5 12h14" />
      </svg>
      Добавить магазин
    </button>
  </div>
</template>

<style scoped>
.shops { padding: 20px 18px; }
h2 { font-size: 19px; margin: 0 0 8px; }
.lead { font-size: 14px; color: var(--sub); line-height: 1.5; margin: 0 0 20px; }
.shop { display: flex; align-items: center; gap: 14px; margin-bottom: 10px; cursor: pointer; }
.avatar {
  width: 42px; height: 42px; border-radius: 13px; background: var(--accent); color: #fff;
  display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 18px;
  flex-shrink: 0;
}
.info { display: flex; flex-direction: column; gap: 2px; flex-grow: 1; }
.info span { font-size: 12px; }
.on { color: var(--green-text); }
.off { color: var(--sub); }
.add {
  margin-top: 6px; background: var(--accent-soft); color: var(--accent);
}
</style>
