import { describe, expect, it } from 'vitest'
import { DICT } from '../i18n'

// Каждый русский ключ обязан иметь перевод на английский (и наоборот —
// «лишний» английский ключ почти всегда опечатка в одном из словарей)
describe('словарь i18n', () => {
  it('у каждого ключа ru есть ключ en', () => {
    const missingInEn = Object.keys(DICT.ru).filter((k) => !(k in DICT.en))
    expect(missingInEn).toEqual([])
  })

  it('у каждого ключа en есть ключ ru', () => {
    const missingInRu = Object.keys(DICT.en).filter((k) => !(k in DICT.ru))
    expect(missingInRu).toEqual([])
  })

  it('t() подставляет плейсхолдеры', async () => {
    const { t } = await import('../i18n')
    const { setLocale } = await import('../services/locale')
    setLocale('ru')
    DICT.ru['test.hello'] = 'Привет, {name}!'
    DICT.en['test.hello'] = 'Hi, {name}!'
    expect(t('test.hello', { name: 'Мир' })).toBe('Привет, Мир!')
    setLocale('en')
    expect(t('test.hello', { name: 'World' })).toBe('Hi, World!')
    setLocale('ru')
    delete DICT.ru['test.hello']
    delete DICT.en['test.hello']
  })
})
