<template>
  <form class="edit-form">
    <div class="edit-form__header">
      <h2 class="edit-form__heading heading">Редактировать профиль</h2>
      <a class="edit-form__cancel" @click="goBack">Отмена</a>
    </div>

    <div class="edit-form__block">
      <div
        class="edit-form__image-field image-field"
        ref="imageInput"
        :style="{ backgroundImage: 'url(' + profileInfo.image + ')' }"
        @click="triggerFileInput"
      >
        <input
          type="file"
          class="image-field__input"
          @input="handleUploadAvatar"
          id="image_input"
          ref="image"
          hidden
        />

        <div class="image-field__icon-container">
          <Icon
            class="image-field__plus-icon"
            icon="octicon:feed-plus-16"
            v-if="!profileInfo.image"
          />
          <Icon class="image-field__image-icon" icon="mynaui:image" v-if="!profileInfo.image" />

          <button
            v-if="profileInfo.image"
            type="button"
            class="image-field__delete-button"
            @click.stop="removeImage"
          >
            <Icon icon="pepicons-pop:trash" class="image-field__delete-icon" />
          </button>
        </div>
      </div>

      <label class="edit-form__name-field name-field">
        <input
          type="text"
          v-model="profileInfo.name"
          class="name-field__input"
          aria-label="name"
          placeholder="Имя автора"
          maxlength="30"
        />
        <span class="name-field__word-count">{{ profileInfo.name.length }}/30</span>
      </label>
    </div>

    <div class="edit-form__description-field description-field">
      <div class="description-field__info">
        <p class="description-field__text">{{ t('GuideDescription') }}</p>

        <span class="description-field__word-count">{{ profileInfo.description.length }}/40</span>
      </div>

      <textarea
        class="description-field__input"
        maxlength="40"
        v-model="profileInfo.description"
        required
      />
    </div>

    <div class="edit-form__link link-field">
      <p class="link-field__text">Ссылка</p>

      <div class="link-field__name-field">
        <input
          type="text"
          v-model="profileInfo.linkName"
          class="link-field__name-input"
          aria-label="link-name"
          placeholder="Имя автора"
          maxlength="30"
        />
      </div>

      <div class="link-field__url-field">
        <input
          type="text"
          v-model="profileInfo.linkUrl"
          class="link-field__url-input"
          aria-label="url"
          placeholder="Имя автора"
          maxlength="30"
        />

        <button type="button" class="link-field__paste-button" @click="pasteFromClipboard">
          <Icon icon="icon-park-outline:share" class="link-field__paste-icon" />
        </button>
      </div>
    </div>

    <button
      @click="handleSaveProfile"
      class="edit-form__submit-button submit-button"
      type="submit"
      :disabled="isLoading"
    >
      Готово
    </button>
  </form>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Icon } from '@iconify/vue'

import { getProfileInfo, saveProfile, uploadAvatar } from '@/api'

const { t } = useI18n({ useScope: 'global' })

const profileInfo = ref({
  image: '/default-profile.png',
  name: '',
  description: '',
  linkName: '',
  linkUrl: ''
})

function removeImage() {
  profileInfo.value.image = null
}

const avatarInput = ref(null)
const router = useRouter()

function goBack() {
  router.back()
}

function triggerFileInput() {
  avatarInput.value?.click()
}

async function handleUploadAvatar(event) {
  const file = event.target.files[0]
  if (!file) return

  const formData = new FormData()
  formData.append('file', file)

  try {
    const response = await uploadAvatar(formData)

    if (response.status === 200) {
      profileInfo.value.image = URL.createObjectURL(file)
      console.log('Avatar updated successfully!')
    }
  } catch (error) {
    console.error('Ошибка при загрузке аватара:', error)
  }
}

async function handleSaveProfile() {
  try {
    const response = await saveProfile(profileInfo.value)

    if (response.status === 200) {
      console.log('Profile updated successfully!')
      router.push('/earn')
    }
  } catch (error) {
    console.error('Error updating profile:', error)
  }
}

async function handleGetProfileInfo() {
  const IMAGE_UPLOAD_URL = process.env.VUE_APP_IMAGE_UPLOAD_URL

  try {
    const data = await getProfileInfo()

    profileInfo.value.name = data.firstName || ''
    profileInfo.value.description = data.description || ''
    profileInfo.value.image =
      `${IMAGE_UPLOAD_URL}/profiles/${data.username}.jpg` || '/default-profile.png'
    profileInfo.value.linkName = data.linkName || ''
    profileInfo.value.linkUrl = data.linkUrl || ''
  } catch (error) {
    console.error('Error fetching profile info:', error)
  }
}

const pasteFromClipboard = async () => {
  try {
    if (navigator.clipboard) {
      const text = await navigator.clipboard.readText()
      profileInfo.value.linkUrl = text
    } else {
      console.warn('Clipboard API not supported')
    }
  } catch (error) {
    console.error('Failed to read clipboard content:', error)
  }
}

onMounted(async () => {
  await handleGetProfileInfo()
})
</script>

<style scoped lang="scss" src="./EditProfile.scss" />
