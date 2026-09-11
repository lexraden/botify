<script setup>
/**
 * Реквизиты магазина для приёма переводов — отдельный экран кабинета.
 *
 * Функция тарифа Pro: без него список не заводится, и экран показывает,
 * что это даёт. Деньги по таким заказам идут напрямую продавцу, платформа
 * их не видит и комиссию не берёт — об этом сказано прямо на экране, чтобы
 * не выяснялось после первой продажи.
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  deletePaymentMethod,
  fetchPaymentMethods,
  fetchShopSummary,
  savePaymentMethod,
} from '../api'
import { t } from '../i18n'
import { apiError } from '../services/apiError'
import PlanModal from '../components/PlanModal.vue'

const KINDS = ['card', 'sbp', 'crypto', 'other']
const MAX = 8

const route = useRoute()
const router = useRouter()
const botId = computed(() => route.params.botId)

const methods = ref([])
const error = ref('')
const saving = ref(false)
const planOpen = ref(false)
// Тариф не подошёл: список отдаётся всем, а вот завести способ можно только
// на Pro — узнаём об этом по отказу сервера, а не гадаем на фронте.
const proRequired = ref(false)

// null — форма закрыта; иначе черновик способа (новый или редактируемый)
const draft = ref(null)

// Комиссия магазина — для сравнения способов. Берём с сервера, а не пишем
// «5%» в текст: ставка у магазинов может отличаться.
const commission = ref(null)

async function reload() {
  try {
    methods.value = await fetchPaymentMethods(botId.value)
  } catch (e) {
    error.value = apiError(e, 'seller.loadError')
  }
}
onMounted(async () => {
  await reload()
  try {
    commission.value = Number((await fetchShopSummary(botId.value)).commission_pct)
  } catch {
    /* без ставки просто не рисуем сравнение */
  }
})

function startNew() {
  if (methods.value.length >= MAX) {
    error.value = t('req.max', { n: MAX })
    return
  }
  error.value = ''
  draft.value = { kind: 'card', label: '', account: '', holder: '', note: '', is_active: true }
}

function startEdit(m) {
  error.value = ''
  draft.value = { ...m, holder: m.holder || '', note: m.note || '' }
}

async function save() {
  const d = draft.value
  if (saving.value) return
  if (!d.label.trim() || !d.account.trim()) {
    error.value = t('req.required')
    return
  }
  saving.value = true
  error.value = ''
  try {
    await savePaymentMethod(botId.value, {
      ...d,
      label: d.label.trim(),
      account: d.account.trim(),
      holder: d.holder.trim() || null,
      note: d.note.trim() || null,
    })
    draft.value = null
    await reload()
  } catch (e) {
    if (e.response?.status === 403 && e.response?.data?.detail === 'pro_required') {
      proRequired.value = true
      draft.value = null
    } else {
      error.value = apiError(e, 'req.saveError')
    }
  } finally {
    saving.value = false
  }
}

async function remove(m) {
  if (!window.confirm(t('req.deleteConfirm', { label: m.label }))) return
  try {
    await deletePaymentMethod(botId.value, m.id)
    await reload()
  } catch (e) {
    error.value = apiError(e, 'req.saveError')
  }
}
</script>

<template>
  <div class="req">
    <div class="top">
      <a class="back" @click="router.push(`/shop/${botId}`)">← {{ t('seller.backToShop') }}</a>
    </div>

    <div class="who">
      <div class="avatar">💳</div>
      <h2>{{ t('req.title') }}</h2>
    </div>

    <p class="lead">{{ t('req.lead') }}</p>

    <!-- Ради чего это всё: сравнение в деньгах, а не обещанием в описании
         тарифа. Ставка берётся с сервера — она у магазинов разная. -->
    <div v-if="commission !== null" class="compare">
      <div class="col">
        <span class="cap">{{ t('pay.crypto') }}</span>
        <b class="pct">−{{ commission }}%</b>
        <span class="sub">{{ t('req.viaPlatform') }}</span>
      </div>
      <div class="col win">
        <span class="cap">{{ t('pay.transfer') }}</span>
        <b class="pct">0%</b>
        <span class="sub">{{ t('req.direct') }}</span>
      </div>
    </div>
    <p v-if="commission !== null" class="compare-note">
      {{ t('req.compareNote', { sum: (100 - commission).toFixed(0) }) }}
    </p>

    <!-- отказ по тарифу: не прячем экран, а объясняем, чего не хватает -->
    <div v-if="proRequired" class="card pro">
      <b>{{ t('req.proOnly') }}</b>
      <button class="btn btn-primary" @click="planOpen = true">{{ t('req.proUpgrade') }}</button>
    </div>

    <p v-if="error" class="error-line">{{ error }}</p>

    <div v-for="m in methods" :key="m.id" class="card row">
      <div class="info">
        <b>{{ m.label }}</b>
        <span class="muted">{{ t(`pay.kind.${m.kind}`) }} · {{ m.account }}</span>
        <span v-if="m.holder" class="muted">{{ t('pay.holder') }}: {{ m.holder }}</span>
        <span v-if="!m.is_active" class="muted off">{{ t('req.hidden') }}</span>
      </div>
      <div class="actions">
        <button class="link" @click="startEdit(m)">{{ t('req.edit') }}</button>
        <button class="link danger" @click="remove(m)">{{ t('req.delete') }}</button>
      </div>
    </div>

    <p v-if="!methods.length && !draft" class="empty">{{ t('req.empty') }}</p>

    <!-- форма: та же и для нового способа, и для правки -->
    <div v-if="draft" class="card form">
      <label>
        <span>{{ t('req.kind') }}</span>
        <select v-model="draft.kind">
          <option v-for="k in KINDS" :key="k" :value="k">{{ t(`pay.kind.${k}`) }}</option>
        </select>
      </label>
      <label>
        <span>{{ t('req.label') }}</span>
        <input v-model="draft.label" :placeholder="t('req.labelPh')" maxlength="64" />
      </label>
      <label>
        <span>{{ t('req.account') }}</span>
        <input v-model="draft.account" :placeholder="t('req.accountPh')" maxlength="128" />
      </label>
      <label>
        <span>{{ t('req.holder') }}</span>
        <input v-model="draft.holder" :placeholder="t('req.holderPh')" maxlength="64" />
      </label>
      <label>
        <span>{{ t('req.note') }}</span>
        <input v-model="draft.note" :placeholder="t('req.notePh')" maxlength="200" />
      </label>
      <label class="check">
        <input v-model="draft.is_active" type="checkbox" />
        <span>{{ t('req.active') }}</span>
      </label>
      <div class="form-actions">
        <button class="btn btn-soft" @click="draft = null">{{ t('common.close') }}</button>
        <button class="btn btn-primary" :disabled="saving" @click="save">
          {{ saving ? t('req.saving') : t('req.save') }}
        </button>
      </div>
    </div>

    <button v-else class="btn btn-primary add" @click="startNew">{{ t('req.add') }}</button>

    <PlanModal v-if="planOpen" @close="planOpen = false" @paid="planOpen = false" />
  </div>
</template>

<style scoped lang="scss">
.req { padding: 18px 16px 36px; }
.top { display: flex; margin-bottom: 14px; }
.back { color: var(--sub); font-size: 14px; font-weight: 700; cursor: pointer; }
.who { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.who h2 { font-size: 18px; margin: 0; }
.avatar {
  width: 52px; height: 52px; border-radius: 17px; background: var(--accent);
  display: flex; align-items: center; justify-content: center; font-size: 24px; flex-shrink: 0;
}
.lead { margin: 0 0 14px; font-size: 13px; color: var(--sub); line-height: 1.5; }
.compare { display: flex; gap: 10px; margin-bottom: 8px; }
.compare .col {
  flex: 1; display: flex; flex-direction: column; gap: 2px;
  border: 1px solid var(--border); border-radius: 14px; padding: 11px 12px;
  background: var(--surface);
}
.compare .col.win { border-color: var(--green); background: var(--green-soft); }
.compare .cap { font-size: 12px; color: var(--sub); font-weight: 700; }
.compare .pct { font-size: 22px; line-height: 1.1; }
.compare .col.win .pct { color: var(--green-text); }
.compare .sub { font-size: 11px; color: var(--sub); line-height: 1.35; }
.compare-note { margin: 0 0 14px; font-size: 12px; color: var(--sub); line-height: 1.45; }
.muted { font-size: 13px; color: var(--sub); word-break: break-all; }
.muted.off { color: var(--orange-text); }
.error-line { color: var(--red); font-size: 13px; font-weight: 600; margin: 0 0 10px; }
.empty { color: var(--sub); font-size: 13px; margin: 10px 0 14px; line-height: 1.5; }
.pro { display: flex; flex-direction: column; gap: 10px; margin-bottom: 12px; }
.row {
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: 10px; margin-bottom: 10px;
}
.info { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.actions { display: flex; flex-direction: column; gap: 6px; flex-shrink: 0; }
.link {
  border: 0; background: none; color: var(--accent); font-size: 13px;
  font-weight: 700; cursor: pointer; padding: 0;
  &.danger { color: var(--red); }
}
.form { display: flex; flex-direction: column; gap: 10px; margin-bottom: 12px; }
.form label { display: flex; flex-direction: column; gap: 4px; font-size: 13px; }
.form label span { color: var(--sub); }
.form label.check { flex-direction: row; align-items: center; gap: 8px; }
.form-actions { display: flex; gap: 8px; }
.form-actions .btn { flex: 1; }
.add { width: 100%; }
</style>
