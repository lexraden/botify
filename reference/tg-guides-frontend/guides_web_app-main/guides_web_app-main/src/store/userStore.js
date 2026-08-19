import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authUser } from '@/api'

export const useUserStore = defineStore('user', () => {
  const userInfoState = ref({})
  const token = ref('')
  const username = ref('')

  const userInfo = computed(() => userInfoState.value)

  async function authenticateUser(params) {
    const result = await authUser(params)
    token.value = result.token
    username.value = result.username
    localStorage.setItem('token', result.token)
    return result
  }

  return {
    userInfoState,
    token,
    username,
    userInfo,
    authenticateUser
  }
})
