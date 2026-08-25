<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { fetchMyOrders } from '../api'
import BrandBadge from '../components/BrandBadge.vue'
import { openTelegramLink, tg } from '../services/telegram'

const router = useRouter()
// null = ещё не загрузили; число — сколько покупок всего
const ordersCount = ref(null)

// initDataUnsafe используем только чтобы поздороваться: сервер личность из
// него не берёт, авторизация — по подписанному initData на каждом запросе.
const me = tg?.initDataUnsafe?.user ?? null

const SUPPORT_URL = 'https://t.me/Botifyapp_bot'

onMounted(async () => {
  try {
    ordersCount.value = (await fetchMyOrders()).length
  } catch {
    ordersCount.value = null // профиль и без счётчика полезен
  }
})
</script>

<template>
  <div class="profile">
    <a class="back" @click="router.push('/')">← В каталог</a>

    <div class="who">
      <img v-if="me?.photo_url" class="avatar" :src="me.photo_url" :alt="me.first_name" />
      <div v-else class="avatar letter">
        {{ (me?.first_name || '?').charAt(0).toUpperCase() }}
      </div>
      <div>
        <h2>{{ me?.first_name || 'Покупатель' }}</h2>
        <span class="muted">покупатель</span>
      </div>
    </div>

    <button class="menu-item" @click="router.push('/my-orders')">
      <span>🛍 Мои покупки</span>
      <span v-if="ordersCount != null" class="count">{{ ordersCount }}</span>
    </button>

    <button class="menu-item" @click="openTelegramLink(SUPPORT_URL)">
      <span>💬 Поддержка</span>
      <span class="muted">написать</span>
    </button>

    <!-- нижний отступ с запасом под фиксированную плашку «Сделано через Botify» -->
    <BrandBadge />
  </div>
</template>

<style scoped lang="scss">
.profile { padding: 18px 16px 76px; }
.back {
  display: inline-block; margin-bottom: 14px; color: var(--sub);
  font-size: 14px; font-weight: 700; cursor: pointer;
}
.who {
  display: flex; align-items: center; gap: 12px; margin-bottom: 18px;
  h2 { font-size: 18px; margin: 0; }
}
.avatar {
  width: 52px; height: 52px; border-radius: 17px; object-fit: cover; flex-shrink: 0;
  &.letter {
    background: var(--accent); color: #fff; display: flex; align-items: center;
    justify-content: center; font-size: 22px; font-weight: 800;
  }
}
.muted { font-size: 13px; color: var(--sub); }
.menu-item {
  width: 100%; box-sizing: border-box; border: 1px solid var(--border); background: var(--surface);
  border-radius: 13px; padding: 15px 14px; margin-bottom: 10px; color: var(--text);
  display: flex; justify-content: space-between; align-items: center;
  font-size: 15px; font-weight: 700; cursor: pointer;
}
.count {
  min-width: 26px; text-align: center; background: var(--surface2); border-radius: 999px;
  padding: 4px 8px; font-size: 13px; font-weight: 800;
}
</style>
