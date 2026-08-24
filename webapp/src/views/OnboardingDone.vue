<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const botId = computed(() => String(route.query.bot || ''))
const username = computed(() => String(route.query.username || ''))

function next() {
  router.replace(botId.value ? `/shop/${botId.value}` : '/shops')
}
</script>

<template>
  <div class="step">
    <div class="emoji">🎉</div>
    <h2>Магазин создан!</h2>
    <p class="lead">
      {{ username ? `@${username} готов принимать заказы` : 'Магазин готов принимать заказы' }}
    </p>
    <p class="sub">Осталось наполнить каталог — и можно продавать.</p>

    <div class="actions">
      <button class="btn btn-primary" @click="next">Далее</button>
    </div>
  </div>
</template>

<style scoped>
.step { padding: 20px 18px 110px; }
.emoji {
  width: 74px;
  height: 74px;
  border-radius: 24px;
  background: var(--accent-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 38px;
  margin: 26px 0 20px;
}
h2 { font-size: 23px; margin: 0 0 10px; line-height: 1.2; }
.lead { font-size: 15px; color: var(--sub); line-height: 1.5; margin: 0; }
.sub { font-size: 14px; color: var(--sub); line-height: 1.5; margin: 8px 0 0; }
.actions {
  position: fixed; left: 0; right: 0; bottom: 0; padding: 14px 18px 24px;
  display: flex; flex-direction: column; gap: 10px; background: var(--bg);
}
</style>
