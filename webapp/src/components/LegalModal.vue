<script setup>
// Модалка юридического документа (ToS / Privacy Policy): та же механика, что у
// TermsModal в онбординге — полный экран, переключатель языка, скролл внутри
// листа. Отличия: проп docs ({ru, en}) вместо зашитых условий продавца,
// юридическое предупреждение в начале и автоматическая нумерация разделов.
import { computed } from 'vue'
import { LOCALES, locale, setLocale } from '../services/locale'

const props = defineProps({
  docs: { type: Object, required: true }, // { ru: {...}, en: {...} }
})
defineEmits(['close'])

const doc = computed(() => props.docs[locale.value])
</script>

<template>
  <Transition name="fade">
    <div class="overlay" @click.self="$emit('close')">
      <div class="sheet" role="dialog" aria-modal="true" :aria-label="doc.modalTitle">
        <header class="head">
          <h3>{{ doc.modalTitle }}</h3>
          <div class="switch" role="group" aria-label="Язык / Language">
            <button
              v-for="l in LOCALES"
              :key="l"
              type="button"
              :class="{ active: locale === l }"
              @click="setLocale(l)"
            >
              {{ l.toUpperCase() }}
            </button>
          </div>
          <button class="close" type="button" aria-label="Закрыть" @click="$emit('close')">✕</button>
        </header>

        <div class="body">
          <p class="notice">{{ doc.notice }}</p>
          <section v-for="(section, i) in doc.sections" :key="i">
            <h4>{{ i + 1 }}. {{ section.title }}</h4>
            <p v-for="(item, j) in section.items" :key="j">{{ item }}</p>
          </section>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  z-index: 90; /* ниже глобального лоадера (100) */
  background: color-mix(in srgb, var(--bg) 55%, transparent);
  backdrop-filter: blur(2px);
}
.sheet {
  position: absolute;
  inset: 0; /* во весь экран — без зазора сверху */
  display: flex;
  flex-direction: column;
  background: var(--surface);
  animation: slide-up 0.22s ease;
}
.head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
}
.head h3 {
  flex: 1;
  font-size: 15px;
  margin: 0;
}
.switch {
  display: flex;
  gap: 3px;
  background: var(--surface2);
  border-radius: 11px;
  padding: 3px;
}
.switch button {
  border: 0;
  border-radius: 8px;
  padding: 5px 9px;
  font-size: 11px;
  font-weight: 800;
  color: var(--sub);
  background: transparent;
  cursor: pointer;
}
.switch .active {
  background: var(--surface);
  color: var(--text);
  box-shadow: 0 1px 4px rgba(20, 22, 27, 0.14);
}
.close {
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  border: 0;
  border-radius: 11px;
  background: var(--surface2);
  color: var(--text);
  font-size: 14px;
  cursor: pointer;
}
.body {
  flex: 1;
  min-height: 0; /* даёт скроллиться внутри листа фиксированной высоты */
  overflow-y: auto;
  padding: 4px 18px 28px;
}
.notice {
  margin: 14px 0 0;
  padding: 10px 12px;
  border-radius: 11px;
  background: var(--surface2);
  font-size: 12.5px;
  line-height: 1.55;
  color: var(--sub);
}
.body section {
  margin-top: 16px;
}
.body h4 {
  font-size: 13.5px;
  margin: 0 0 6px;
}
.body p {
  font-size: 13px;
  line-height: 1.55;
  color: var(--sub);
  margin: 0;
}
.body section p + p {
  margin-top: 8px; /* подпункты раздела не слипаются */
}
@keyframes slide-up {
  from { transform: translateY(24px); opacity: 0.6; }
  to { transform: translateY(0); opacity: 1; }
}
.fade-enter-active, .fade-leave-active { transition: opacity 0.18s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
