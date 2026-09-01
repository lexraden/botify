<script setup>
import { computed, onMounted, ref } from 'vue'
import { createSubscriptionInvoice, fetchSubscription } from '../api'
import { t } from '../i18n'
import { apiError } from '../services/apiError'
import { openTelegramLink, tg } from '../services/telegram'

// reason: 'products' | 'services' | 'mailing' | null — что именно упёрлось;
// null значит, что окно открыли сами, из карточки тарифа
const props = defineProps({ reason: { type: String, default: null } })
const emit = defineEmits(['close', 'paid'])

const info = ref(null)
const error = ref('')
const busy = ref('')

onMounted(async () => {
  try {
    info.value = await fetchSubscription()
  } catch (e) {
    error.value = apiError(e, 'plan.loadError')
  }
})

const plans = computed(() =>
  info.value
    ? [
        {
          id: 'pro',
          title: 'Pro',
          usdt: Number(info.value.price_usdt),
          stars: info.value.price_stars,
          perks: [t('plan.perkUnlimited'), t('plan.perkMailing')],
        },
        {
          id: 'plus',
          title: 'Plus',
          usdt: Number(info.value.plus_price_usdt),
          stars: info.value.plus_price_stars,
          perks: [t('plan.perkUnlimited'), t('plan.perkMailing'), t('plan.perkP2P')],
        },
      ]
    : [],
)

async function pay(plan, method) {
  if (busy.value) return
  busy.value = `${plan}:${method}`
  error.value = ''
  try {
    const out = await createSubscriptionInvoice(method, plan)
    if (out.payment_url) {
      // счёт в @CryptoBot — уводим туда, как и при оплате заказа
      openTelegramLink(out.payment_url)
      emit('close')
    } else if (out.stars_link) {
      // звёзды оплачиваются нативным окном поверх приложения; закрывать его
      // рано нельзя — иначе продавец не увидит результата
      tg?.openInvoice?.(out.stars_link, (status) => {
        if (status === 'paid') emit('paid')
      })
      if (!tg?.openInvoice) openTelegramLink(out.stars_link)
    }
  } catch (e) {
    error.value = apiError(e, 'plan.invoiceError')
  } finally {
    busy.value = ''
  }
}
</script>

<template>
  <div class="backdrop" @click.self="emit('close')">
    <div class="sheet" role="dialog" aria-modal="true">
      <h3>{{ reason ? t(`plan.limit.${reason}`) : t('plan.upgradeTitle') }}</h3>
      <!-- ничего не пропадает: лимит останавливает рост, а не отбирает
           накопленное — об этом говорим прямо, иначе окно пугает -->
      <p class="lead">{{ t('plan.nothingLost') }}</p>

      <div v-for="p in plans" :key="p.id" class="tier">
        <div class="tier-head">
          <b>{{ p.title }}</b>
          <span class="price">{{ p.usdt }} USDT / {{ info.period_days }} {{ t('plan.days') }}</span>
        </div>
        <ul>
          <li v-for="perk in p.perks" :key="perk">{{ perk }}</li>
        </ul>
        <button
          class="btn btn-primary"
          :disabled="!info.crypto_available || busy === `${p.id}:crypto`"
          @click="pay(p.id, 'crypto')"
        >
          {{ busy === `${p.id}:crypto` ? '…' : t('plan.payUsdt', { sum: p.usdt }) }}
        </button>
        <button class="btn btn-soft stars" :disabled="busy === `${p.id}:stars`" @click="pay(p.id, 'stars')">
          {{ busy === `${p.id}:stars` ? '…' : t('plan.payStars', { n: p.stars }) }}
        </button>
      </div>

      <p v-if="error" class="error">{{ error }}</p>
      <button class="btn btn-soft close" @click="emit('close')">{{ t('common.close') }}</button>
    </div>
  </div>
</template>

<style scoped>
.backdrop {
  position: fixed; inset: 0; z-index: 60;
  background: rgba(10, 10, 16, 0.6);
  display: flex; align-items: flex-end; justify-content: center;
}
.sheet {
  width: 100%; max-width: 520px; max-height: 92vh; overflow-y: auto;
  background: var(--bg); border-radius: 20px 20px 0 0; padding: 20px 16px 24px;
  display: flex; flex-direction: column; gap: 12px;
}
h3 { margin: 0; font-size: 18px; }
.lead { margin: 0; font-size: 13.5px; color: var(--sub); }
.tier {
  border: 1px solid var(--border); border-radius: 15px;
  padding: 14px 15px; display: flex; flex-direction: column; gap: 9px;
}
.tier-head { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
.tier-head b { font-size: 16px; }
.price { font-size: 13px; color: var(--sub); white-space: nowrap; }
ul { margin: 0; padding-left: 18px; display: flex; flex-direction: column; gap: 4px; font-size: 13.5px; }
.stars { border: 1px solid var(--border); }
.error { color: var(--red); font-size: 13px; margin: 0; }
.close { margin-top: 2px; }
</style>
