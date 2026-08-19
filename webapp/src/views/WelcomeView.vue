<script setup>
import { useRouter } from 'vue-router'
import { markIntroSeen } from '../services/intro'

const router = useRouter()

function start() {
  markIntroSeen()
  router.replace('/onboarding/payment')
}
</script>

<template>
  <div class="welcome">
    <h1>Твой магазин внутри Telegram</h1>
    <p class="lead">Твой бот, твои клиенты, твои деньги</p>

    <div class="hero">
      <div class="card preview">
        <div class="cover">📕</div>
        <div class="meta">
          <b>Гайд по обжарке</b>
          <span class="muted">digital · придёт в чат</span>
        </div>
        <div class="price">15 USDT</div>
      </div>
      <div class="paid">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">
          <path d="M20 6L9 17l-5-5" />
        </svg>
        Оплачено
      </div>
    </div>

    <div class="chips">
      <span>Без сайта</span>
      <span>Быстрая оплата</span>
      <span>Своя база</span>
    </div>

    <div class="actions">
      <button class="btn btn-primary" @click="start">
        Начать
        <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M5 12h14" /><path d="M13 6l6 6-6 6" />
        </svg>
      </button>
      <div class="note">2 шага · ~10 минут</div>
    </div>
  </div>
</template>

<style scoped>
.welcome { padding: 22px 20px 130px; }
h1 {
  font-size: 26px; line-height: 1.2; margin: 8px 0 12px;
}
.lead { font-size: 16px; font-weight: 600; color: var(--sub); line-height: 1.45; margin: 0; }
.hero { position: relative; display: flex; justify-content: center; margin-top: 32px; }
.preview {
  width: 200px; display: flex; flex-direction: column; gap: 11px;
  transform: rotate(-4deg); box-shadow: var(--shadow);
}
.cover {
  height: 86px; border-radius: 16px; background: var(--surface2);
  display: flex; align-items: center; justify-content: center; font-size: 48px;
}
.meta { display: flex; flex-direction: column; gap: 3px; }
.meta b { font-size: 14px; }
.meta .muted { font-size: 12px; }
.price {
  background: var(--accent); color: #fff; border-radius: 12px; height: 38px;
  display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 800;
}
.paid {
  position: absolute; right: 14px; top: 4px; transform: rotate(3deg);
  display: flex; align-items: center; gap: 7px;
  background: var(--green-soft); color: var(--green-text); border: 1px solid var(--border);
  border-radius: 14px; padding: 9px 13px; font-size: 13px; font-weight: 800;
}
.chips { display: flex; gap: 8px; justify-content: center; flex-wrap: wrap; margin-top: 34px; }
.chips span {
  background: var(--surface2); border-radius: 20px; padding: 9px 14px;
  font-size: 13px; font-weight: 700;
}
.actions {
  position: fixed; left: 0; right: 0; bottom: 0; padding: 14px 20px 26px;
  display: flex; flex-direction: column; gap: 10px; background: var(--bg);
}
.note { font-size: 13px; font-weight: 600; color: var(--sub); text-align: center; }
</style>
