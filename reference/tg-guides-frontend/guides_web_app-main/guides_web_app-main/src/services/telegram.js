import axios from 'axios'
import { useUserStore } from '@/store/userStore'

const TONCENTER_API = process.env.VUE_APP_TONCENTER_API

const userStore = useUserStore()

function saveToken(token) {
  localStorage.setItem('authToken', token)
}

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

export async function setUser() {
  const tgWebApp = window.Telegram.WebApp
  tgWebApp.ready()
  const tgUnsafeData = tgWebApp.initDataUnsafe

  if (!tgUnsafeData || !tgUnsafeData.user) {
    console.error('Нет данных пользователя в initDataUnsafe:', tgUnsafeData)
    return
  }

  const params = {
    firstName: tgUnsafeData.user.first_name || 'Unknown',
    id: tgUnsafeData.user.id || 0,
    lastName: tgUnsafeData.user.last_name || 'Unknown',
    username: tgUnsafeData.user.username || 'Unknown'
  }
  await authenticateUser(params)
}

export async function fetchBalance(address) {
  try {
    const response = await axios.get(`${TONCENTER_API}/getAddressBalance?address=${address}`)
    const balanceInTon = response.data.result / 1e9

    console.log('Balance:', balanceInTon)
    return balanceInTon.toFixed(3)
  } catch (error) {
    console.error('Error fetching balance:', error)
  }
}
