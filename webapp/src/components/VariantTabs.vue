<script setup>
import { computed } from 'vue'
import { t } from '../i18n'

// Переключатель вариаций: компактные квадратные кнопки плюс «добавить».
// Подпись — свойства вариации («Красный · M»), пока их не задали — номер.
const props = defineProps({
  variants: { type: Array, required: true },
  active: { type: Number, required: true },
})
const emit = defineEmits(['select', 'add'])

const labels = computed(() =>
  props.variants.map((v, i) => {
    const filled = Object.values(v.attributes || {})
      .map((x) => String(x).trim())
      .filter(Boolean)
    return filled.length ? filled.join(' · ') : t('form.variantN', { n: i + 1 })
  }),
)
</script>

<template>
  <div class="variant-tabs">
    <button
      v-for="(label, i) in labels"
      :key="i"
      type="button"
      class="tab"
      :class="{ active: i === active, off: variants[i].is_active === false }"
      :title="label"
      @click="emit('select', i)"
    >
      <span class="num">{{ i + 1 }}</span>
      <span class="label">{{ label }}</span>
    </button>

    <button type="button" class="tab add" :aria-label="t('form.addVariant')" @click="emit('add')">
      <span class="plus">+</span>
      <span class="label">{{ t('form.addVariant') }}</span>
    </button>
  </div>
</template>

<style scoped>
.variant-tabs {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding: 2px 0 6px;
  /* полоса прокрутки съедала бы высоту ряда на десктопе */
  scrollbar-width: none;
}
.variant-tabs::-webkit-scrollbar { display: none; }
.tab {
  flex: 0 0 auto;
  width: 76px;
  height: 76px;
  border-radius: 15px;
  border: 1.5px solid var(--line, var(--border));
  background: var(--surface2);
  color: var(--text);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 6px 5px;
}
.tab.active { border-color: var(--accent); background: var(--accent-soft); color: var(--accent); }
/* выключенная вариация видна, но приглушена — её просто не покупают */
.tab.off { opacity: 0.5; }
.num { font-size: 15px; font-weight: 800; line-height: 1; }
.plus { font-size: 24px; font-weight: 700; line-height: 1; color: var(--accent); }
.label {
  font-size: 10px;
  line-height: 1.2;
  text-align: center;
  max-width: 100%;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  word-break: break-word;
}
.tab.add { border-style: dashed; border-color: var(--accent); }
</style>
