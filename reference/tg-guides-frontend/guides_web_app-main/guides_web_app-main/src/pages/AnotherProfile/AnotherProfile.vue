<template>
  <div class="another-profile-page">
    <div class="another-profile-page__header">
      <button type="button" @click="goBack" class="another-profile-page__back-button">
        <Icon icon="fluent:ios-arrow-left-24-filled" class="another-profile-page__back-icon" />
      </button>

      <h2 class="another-profile-page__heading heading">{{ t('Profile') }}</h2>
    </div>

    <div>
      <h3 class="another-profile-page__subheading">{{ t('Profile') }}</h3>
      <div class="another-profile-page__block">
        <div
          :style="{ backgroundImage: 'url(' + profileInfo.image + ')' }"
          class="another-profile-page__avatar"
          alt=""
        ></div>

        <div class="another-profile-page__info">
          <p class="another-profile-page__info-name">{{ profileInfo.name }}</p>
          <p class="another-profile-page__info-description">
            {{ t('GuideDescription') }}: {{ profileInfo.description }}
          </p>
          <p class="another-profile-page__info-link">
            <a
              :href="`https://t.me/${profileInfo.username}`"
              target="_blank"
              rel="noopener noreferrer"
            >
              {{ profileInfo.username }}
            </a>
          </p>
        </div>
      </div>
    </div>

    <div class="another-profile-page__guide-list no-border">
      <h2 class="another-profile-page__guide-heading heading">{{ t('AuthorGuides') }}</h2>

      <GuidesList :items="guides" />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'

import { getProfileByUsername, getUserGuidesByUsername } from '@/api'
import GuidesList from '@/components/GuidesList/GuidesList.vue'

const { t } = useI18n({ useScope: 'global' })
const guides = ref([])
const profileInfo = ref({
  image: '/default-profile.png',
  name: '',
  description: '',
  username: ''
})

const router = useRouter()

function goBack() {
  router.back()
}

onMounted(async () => {
  const username = router.currentRoute.value.params.reflink

  const IMAGE_UPLOAD_URL = process.env.VUE_APP_IMAGE_UPLOAD_URL.replace('/uploads', '')

  const data = await getProfileByUsername(username)
  profileInfo.value.name =
    `${data.firstName} ${data.lastName !== 'Unknown' ? data.lastName : ''}`.trim()
  profileInfo.value.description = data.description || 'Описание отсутствует'
  profileInfo.value.image = data.imageUrl
    ? `${IMAGE_UPLOAD_URL}${data.imageUrl}`
    : '/default-profile.png'
  profileInfo.value.username = data.username || ''

  const guidesData = await getUserGuidesByUsername(username)

  guides.value = guidesData
})
</script>

<style scoped lang="scss" src="./AnotherProfile.scss" />
