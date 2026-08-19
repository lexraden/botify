<template>
  <div class="profile-page">
    <div class="profile-page__header">
      <div class="profile-page__balance">
        <h2 class="profile-page__balance-heading heading">
          <span>{{ t('Balance') }}</span>
          <span class="profile-page__balance-text">
            <TelegramStar size="24" /> <span>{{ profileInfo.balance }}</span>
          </span>
        </h2>

        <button class="profile-page__settings-button" type="button" @click="settings = true">
          <Icon class="profile-page__settings-icon" icon="solar:settings-linear" />
        </button>
      </div>

      <div class="profile-page__balance-buttons balance-buttons">
        <button
          v-if="!walletConnected"
          type="button"
          class="balance-buttons__button-connect"
          @click="connectWallet"
        >
          {{ t('ConnectWallet') }}
        </button>

        <button v-else type="button" class="balance-buttons__button-connect">
          <Icon icon="simple-icons:ton" /> {{ profileInfo2.balance || '0' }} TON
        </button>

        <button type="button" class="balance-buttons__button-withdraw">
          {{ t('WithdrawFunds') }}
        </button>
      </div>
    </div>

    <div class="profile-page__profile profile">
      <div class="profile__header">
        <h2 class="profile__heading">{{ t('Profile') }}</h2>

        <button type="button" class="profile__edit-button" @click="navigateToEditProfile">
          <Icon class="profile__edit-icon" icon="lucide:edit" />
        </button>
      </div>

      <div class="profile__block">
        <div
          :style="{ backgroundImage: 'url(' + profileInfo.image + ')' }"
          class="profile__avatar"
          alt=""
          @click="triggerFileInput"
        ></div>
        <input
          type="file"
          ref="avatarInput"
          @change="handleUploadAvatar"
          accept="image/*"
          style="display: none"
        />

        <div class="profile__info">
          <p class="profile__info-name">{{ profileInfo.name }}</p>
          <p class="profile__info-description" v-if="!editMode">
            {{ t('GuideDescription') }}: {{ profileInfo.description }}
          </p>
          <input
            v-if="editMode"
            v-model="profileInfo.description"
            class="edit-input"
            @blur="handleSaveDescription"
          />
          <p class="profile__info-link">
            {{ profileInfo.link.name }}:
            <a :href="profileInfo.link.url" target="_blank" rel="noopener noreferrer">
              {{ profileInfo.username }}
            </a>
          </p>
        </div>
      </div>
    </div>

    <div class="profile-page__my-guides my-guides no-border">
      <h2 class="my-guides__heading heading">{{ t('MyGuides') }}</h2>

      <div class="my-guides__carousel">
        <MyGuideItem v-for="item in guides" :item="item" :key="item.id" />
      </div>
    </div>

    <div class="profile-page__referrals referrals no-border">
      <h2 class="referrals__heading heading">{{ t('Referals') }}</h2>

      <p class="referrals__link-info">
        <span class="referrals__link">{{ t('ReferalLink') }}</span>
        <button type="button" class="referrals__link-button" @click="copyReferralLink">
          <a @click.stop :href="referralFullLink" target="_blank">{{ profileInfo.referal.link }}</a>
          <Icon class="referrals__link-icon" icon="basil:copy-outline" />
        </button>
      </p>

      <div class="referrals__list">
        <div
          class="referrals__list-item"
          v-for="item in profileInfo.referal.referals"
          :key="item.id"
        >
          <div class="referrals__list-item-info">
            <img :src="item.image" alt="" class="referral__list-item-avatar" />
            <span class="name">{{ item.name }}</span>
          </div>

          <div class="referrals__list-item-stats">
            <span class="referrals__list-item-stats-stars"
              ><TelegramStar size="17" /> +{{ item.statPerWeek }}
            </span>
            <span class="time-period"> {{ t('EarnedPerWeek') }}</span>
          </div>
        </div>
      </div>
    </div>

    <div class="profile-page__drawer drawer no-border" :class="{ drawer_open: settings == true }">
      <div class="drawer__header">
        <h2 class="drawer__heading heading">
          {{ t('Settings') }}
        </h2>

        <button class="drawer__close-button" type="button" @click="settings = false">
          <Icon class="drawer__close-icon" icon="material-symbols:close" />
        </button>
      </div>

      <div class="drawer__fields">
        <div class="drawer__langugage-field">
          <div class="drawer__language-text">
            <Icon class="drawer__language-icon" icon="material-symbols-light:language" />
            <span>{{ t('Language') }} </span>
          </div>

          <div class="drawer__language-select-block">
            <select
              class="drawer__language-select"
              name="language"
              id="languageSelect"
              v-model="currLang"
            >
              <option>Русский</option>
              <option>English</option>
            </select>

            <label for="languageSelect">
              <Icon class="drawer__language-select-icon" icon="solar:alt-arrow-down-line-duotone" />
            </label>
          </div>
        </div>

        <div class="drawer__theme-field">
          <span class="drawer__theme-text">{{ t('DarkTheme') }}</span>

          <button type="button" class="drawer__theme-button" @click="theme = !theme">
            <p
              class="drawer__theme-toggle"
              :class="{ 'drawer__theme-toggle_off': theme == false }"
            ></p>
          </button>
        </div>
      </div>

      <div class="drawer__documents">
        <a href="#" target="_blank" class="drawer__document-link">{{ t('PrivacyPolicy') }}</a>
        <a href="#" target="_blank" class="drawer__document-link">{{ t('AllRightsReserved') }}</a>
      </div>
    </div>
  </div>
</template>

<script setup>
import { Icon } from '@iconify/vue'
import { onMounted, ref, watch, computed } from 'vue'

import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/store/userStore'
import { getTonConnectUI } from '@/components/tonConnect'
import { TonConnectUIError } from '@tonconnect/ui'
import { getProfileInfo, loadUserTasks, saveDescription, uploadAvatar } from '@/api'
import { fetchBalance } from '@/services/telegram'
import TelegramStar from '@/components/ui/icons/TelegramStar.vue'
import MyGuideItem from '@/components/MyGuideItem/MyGuideItem.vue'

const { t, locale } = useI18n({ useScope: 'global' })
const guides = ref([])
const router = useRouter()
const walletConnected = ref(false)
const profileInfo = ref({
  image: '/default-profile.png',
  name: '',
  description: '',
  link: {
    name: '',
    url: ''
  },
  guides: [],
  referal: {
    link: '',
    referals: []
  }
})
const profileInfo2 = ref({
  balance: 0
})
let tonConnectUI

const referralFullLink = computed(() => {
  return `https://t.me/irlguides_bot?start=${profileInfo.value.referal.link}`
})

function copyReferralLink() {
  const textToCopy = referralFullLink.value

  if (navigator.clipboard) {
    navigator.clipboard
      .writeText(textToCopy)
      .then(() => {
        alert('Реферальная ссылка скопирована!')
      })
      .catch((err) => {
        console.error('Ошибка при копировании через Clipboard API:', err)
        fallbackCopyTextToClipboard(textToCopy)
      })
  } else {
    fallbackCopyTextToClipboard(textToCopy)
  }
}
function fallbackCopyTextToClipboard(text) {
  const textArea = document.createElement('textarea')
  textArea.value = text
  textArea.style.position = 'fixed' // Избегаем прокрутки страницы
  document.body.appendChild(textArea)
  textArea.focus()
  textArea.select()

  try {
    const successful = document.execCommand('copy')
    const msg = successful ? 'успешно' : 'не удалось'
    alert(`Копирование текста ${msg}`)
  } catch (err) {
    console.error('Ошибка при использовании фолбэка:', err)
  }

  document.body.removeChild(textArea)
}
async function connectWallet() {
  try {
    // Убедитесь, что tonConnectUI инициализирован перед использованием
    if (!tonConnectUI) {
      tonConnectUI = await getTonConnectUI() // Инициализируем tonConnectUI, если это еще не сделано
    }

    // Проверка подключения кошелька
    if (tonConnectUI.connected && tonConnectUI.wallet) {
      console.log('Using already connected wallet:', tonConnectUI.wallet)
      walletConnected.value = true
      const balanceInTon = await fetchBalance(tonConnectUI.wallet.account.address)

      profileInfo2.value.balance = balanceInTon
    } else {
      // Подключаем кошелек, если он не подключен
      const connectionResult = await tonConnectUI.connectWallet()
      const wallet = connectionResult.wallet
      if (wallet && wallet.account.address) {
        console.log('Wallet connected:', wallet.account.address)
        walletConnected.value = true
        const balanceInTon = await fetchBalance(wallet.account.address)

        profileInfo2.value.balance = balanceInTon
      } else {
        console.error('Error: Wallet address not found.')
      }
    }
  } catch (error) {
    if (error instanceof TonConnectUIError && error.code === 'WalletAlreadyConnectedError') {
      console.log('Wallet already connected, using the existing connection.')
    } else {
      console.error('Error connecting wallet:', error)
    }
  }
}
function navigateToEditProfile() {
  router.push({ name: 'EditProfile' })
}

const editMode = ref(false)
const avatarInput = ref(null)
const userStore = useUserStore()

async function authenticateUser(params) {
  try {
    const response = await userStore.authenticateUser({ params })
    const token = response.token
    saveToken(token) // Сохраняем токен в localStorage
    console.log('Токен сохранен:', token)
  } catch (error) {
    console.error('Ошибка аутентификации:', error)
  }
}

function saveToken(token) {
  localStorage.setItem('authToken', token)
}
// Функция для передачи данных пользователя
function setUser() {
  const tgWebApp = window.Telegram.WebApp

  // Убедитесь, что Telegram WebApp существует
  if (!tgWebApp) {
    console.error(
      'Telegram WebApp не инициализирован. Убедитесь, что запускаете MiniApp в Telegram.'
    )
    return
  }

  // Инициализируйте WebApp и получите данные
  const tgUnsafeData = tgWebApp.initDataUnsafe

  // Вывод всех данных tgUnsafeData в консоль для проверки
  console.log('Telegram initDataUnsafe:', tgUnsafeData)

  if (!tgUnsafeData || !tgUnsafeData.user) {
    console.error('Нет данных пользователя в initDataUnsafe:', tgUnsafeData)
    return
  }

  // Используем реальные данные из tgUnsafeData
  const params = {
    firstName: tgUnsafeData.user.first_name || 'Unknown',
    id: tgUnsafeData.user.id || 0,
    lastName: tgUnsafeData.user.last_name || 'Unknown',
    username: tgUnsafeData.user.username || 'Unknown'
  }

  console.log('Передаваемые данные пользователя:', params)

  // Авторизация пользователя с использованием данных из MiniApp
  authenticateUser(params)
}

// Функция для получения данных профиля
async function handleGetProfileInfo() {
  const IMAGE_UPLOAD_URL = process.env.VUE_APP_IMAGE_UPLOAD_URL.replace('/uploads', '')

  try {
    const data = await getProfileInfo()

    profileInfo.value.name =
      `${data.firstName} ${data.lastName !== 'Unknown' ? data.lastName : ''}`.trim()
    profileInfo.value.description =
      data.description.replace(/^"(.*)"$/, '$1').replace(/\\"/g, '"') || 'Описание нету'
    profileInfo.value.link.name = 'Мой телеграм'
    profileInfo.value.link.url = 'https://t.me/' + (data.username || '')
    profileInfo.value.username = data.username || ''
    profileInfo.value.image = data.imageUrl
      ? `${IMAGE_UPLOAD_URL}${data.imageUrl}`
      : '/default-profile.png'
    profileInfo.value.balance = data.balance
    profileInfo.value.referal.link = data.referralLink

    // Обработка рефералов
    console.log(data.referrals)
    profileInfo.value.referal.referals = data.referrals.map((ref) => ({
      id: ref.referral.id,
      name: `${ref.referral.firstName || 'Без имени'} ${ref.referral.lastName || ''}`.trim(),
      username: ref.referral.username,
      image: ref.referral.imageUrl
        ? `${IMAGE_UPLOAD_URL}${ref.referral.imageUrl}`
        : '/default-profile.png',
      statPerWeek: ref.referral.balance
    }))
  } catch (error) {
    console.error('Ошибка при получении данных профиля:', error)
  }
}

// Открытие диалога выбора файла
function triggerFileInput() {
  avatarInput.value?.click()
}

// Загрузка аватара
async function handleUploadAvatar(event) {
  const file = event.target.files[0]
  if (!file) return

  const formData = new FormData()
  formData.append('file', file)

  try {
    const response = await uploadAvatar(formData)

    if (response.status === 200) {
      await handleGetProfileInfo()
      window.location.reload()
      console.log('Аватар успешно обновлен!')
    }
  } catch (error) {
    console.error('Ошибка при загрузке аватара:', error)
  }
}

// Сохранение изменений описания
async function handleSaveDescription() {
  editMode.value = false

  try {
    const response = await saveDescription(profileInfo.value.description)

    if (response.status === 200) {
      await handleGetProfileInfo()
      console.log('Описание успешно обновлено!')
    }
  } catch (error) {
    console.error('Ошибка при обновлении описания профиля:', error)
  }
}

const theme = localStorage.getItem('theme') == 'dark' ? ref(true) : ref(false)
const currLang = localStorage.getItem('lang') == 'English' ? ref('English') : ref('Русский')
const settings = ref(false)
const tg = window.Telegram.WebApp

watch(currLang, () => {
  localStorage.setItem('lang', currLang.value)
  currLang.value == 'Русский' ? (locale.value = 'ru') : (locale.value = 'en')
})

watch(theme, () => {
  const doc = document.documentElement
  if (theme.value == true) {
    doc.setAttribute('theme', 'dark')
    localStorage.setItem('theme', 'dark')
  } else {
    document.body.classList.remove('dark')
    doc.setAttribute('theme', 'light')
    localStorage.setItem('theme', 'light')
  }

  setTimeout(() => {
    const color = getComputedStyle(document.body).getPropertyValue('--main-bg')

    tg.setHeaderColor(color)
    tg.setBackgroundColor(color)
    tg.setBottomBarColor(color)
  }, 100)
})

onMounted(async () => {
  try {
    setUser()
    await handleGetProfileInfo()
    const data = await loadUserTasks(true)
    guides.value = data

    tonConnectUI = await getTonConnectUI()
  } catch (error) {
    console.error('Error during TonConnect initialization:', error)
  }
})
</script>

<style scoped lang="scss" src="./ProfilePage.scss" />
