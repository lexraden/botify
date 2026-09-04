<script setup>
// Рассылки — отдельный экран: форма и история уходят из вкладок кабинета,
// освобождая место вкладке «Отзывы».
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { createMailing, fetchMailings } from '../api'
import { t, intlLocale } from '../i18n'

const route = useRoute()
const router = useRouter()
const botId = computed(() => route.params.botId)

const mailings = ref([])
const error = ref('')
const actionError = ref('')
const mailingForm = ref({ text: '', button_text: '', button_url: '', sending: false })

async function reload() {
  try {
    mailings.value = await fetchMailings(botId.value)
  } catch (e) {
    error.value = e.response?.data?.detail || t('seller.loadError')
  }
}

onMounted(reload)

async function submitMailing() {
  const f = mailingForm.value
  if (f.sending || !f.text) return
  f.sending = true
  actionError.value = ''
  try {
    await createMailing(botId.value, {
      text: f.text,
      button_text: f.button_text || null,
      button_url: f.button_url || null,
    })
    mailingForm.value = { text: '', button_text: '', button_url: '', sending: false }
    await reload()
  } catch (e) {
    actionError.value = e.response?.data?.detail || t('seller.mailingError')
  } finally {
    f.sending = false
  }
}

const fmtDateTime = (iso) =>
  new Date(iso).toLocaleString(intlLocale(), {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
</script>

<template>
  <div class="mailings">
    <div class="top">
      <a class="back" @click="router.push(`/shop/${botId}`)">
        ← {{ t('seller.backToShop') }}
      </a>
    </div>

    <div class="who">
      <div class="avatar">📣</div>
      <div>
        <h2>{{ t('mailings.title') }}</h2>
      </div>
    </div>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="actionError" class="error-line">{{ actionError }}</p>

    <div class="card mailing-form">
      <textarea v-model="mailingForm.text" rows="4" :placeholder="t('seller.mailingTextPh')" />
      <input v-model="mailingForm.button_text" :placeholder="t('seller.mailingBtnTextPh')" />
      <input v-model="mailingForm.button_url" :placeholder="t('seller.mailingBtnUrlPh')" />
      <button
        class="btn btn-primary"
        :disabled="mailingForm.sending || !mailingForm.text || (!!mailingForm.button_text !== !!mailingForm.button_url)"
        @click="submitMailing"
      >
        {{ mailingForm.sending ? '…' : t('seller.sendAll') }}
      </button>
    </div>

    <div v-for="m in mailings" :key="m.id" class="card row">
      <div class="info">
        <b>{{ m.text.slice(0, 60) }}{{ m.text.length > 60 ? '…' : '' }}</b>
        <span class="muted">
          {{ { pending: t('mailing.pending'), sending: t('mailing.sending'), done: t('mailing.done') }[m.status] || m.status }}
          <template v-if="m.status === 'done'"> {{ t('seller.deliveredN', { n: m.sent_count }) }}</template>
        </span>
        <span class="muted">{{ fmtDateTime(m.created_at) }}</span>
      </div>
    </div>
    <p v-if="!mailings.length" class="empty">{{ t('seller.noMailings') }}</p>
  </div>
</template>

<style scoped>
.mailings { padding: 18px 16px 36px; }
.top { display: flex; margin-bottom: 14px; }
.back { color: var(--sub); font-size: 14px; font-weight: 700; cursor: pointer; }
.who { display: flex; align-items: center; gap: 12px; margin-bottom: 18px; }
.who h2 { font-size: 18px; margin: 0; }
.avatar {
  width: 52px; height: 52px; border-radius: 17px; background: var(--accent);
  display: flex; align-items: center; justify-content: center; font-size: 24px; flex-shrink: 0;
}
.muted { font-size: 13px; color: var(--sub); }
.error { text-align: center; color: var(--red); margin-top: 16px; }
.error-line { color: var(--red); font-size: 13px; font-weight: 600; margin: 0 0 10px; }
.mailing-form { display: flex; flex-direction: column; gap: 10px; margin-bottom: 12px; }
.mailing-form textarea { resize: none; }
.row { display: flex; align-items: center; margin-bottom: 10px; }
.info { display: flex; flex-direction: column; gap: 3px; }
.info b { overflow: hidden; text-overflow: ellipsis; }
.info span { font-size: 12px; }
.empty { text-align: center; color: var(--sub); margin-top: 24px; }
</style>
