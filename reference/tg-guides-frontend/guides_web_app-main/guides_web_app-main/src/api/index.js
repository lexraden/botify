import axiosInstance from './apiClient'

const IMAGE_UPLOAD_URL = process.env.VUE_APP_IMAGE_UPLOAD_URL

const getAuthHeaders = () => {
  const token = localStorage.getItem('authToken')
  return { Authorization: `${token}` }
}

export function getGuideImageUrl(imageName) {
  const defaultImg =
    'https://www.trustedreviews.com/wp-content/uploads/sites/54/2021/04/Telegram-920x585.png'

  if (imageName) {
    return `${IMAGE_UPLOAD_URL}/guide/${imageName}`
  }
  return defaultImg
}

export async function authUser(params) {
  try {
    const response = await axiosInstance.post('auth/init', { ...params.params })
    return response.data
  } catch (error) {
    console.error('Ошибка при авторизации:', error)
    throw error
  }
}

export async function getProfileByUsername(username) {
  try {
    const response = await axiosInstance.get(`user-profile/profile/username/${username}`, {
      headers: getAuthHeaders()
    })
    const data = response.data

    return data
  } catch (error) {
    console.error('Ошибка при получении данных профиля:', error)
  }
}

export async function getUserGuidesByUsername(username) {
  try {
    const response = await axiosInstance.get(`user-profile/guides/username/${username}`, {
      headers: getAuthHeaders()
    })
    const data = response.data

    return data
  } catch (error) {
    console.error('Ошибка при получении гайдов по имени пользователя:', error)
  }
}

export async function loadTasks() {
  try {
    const response = await axiosInstance.get('guides/all', {
      headers: getAuthHeaders()
    })

    const data = response.data

    return data
  } catch (error) {
    console.error('Ошибка при загрузке задач:', error)
  }
}

export async function loadUserTasks(own) {
  try {
    const response = await axiosInstance.get(`user-profile/guides?own=${own}`, {
      headers: getAuthHeaders()
    })

    const data = response.data

    return data
  } catch (error) {
    console.error('Ошибка при загрузке задач:', error)
  }
}

export async function fetchGuide(guideId) {
  try {
    const response = await axiosInstance.get(`user-profile/guides/${guideId}`, {
      headers: getAuthHeaders()
    })

    const data = response.data

    if (data.mainImg) {
      data.mainImg = `${IMAGE_UPLOAD_URL}/guide/${data.mainImg}`
    }

    data.chapters.forEach((chapter) => {
      if (chapter.img) {
        chapter.img = `${IMAGE_UPLOAD_URL}/chapter/image/${chapter.img}`
      }

      if (chapter.video) {
        chapter.video = `${IMAGE_UPLOAD_URL}/chapter/video/${chapter.video}`
      }
    })

    return data
  } catch (error) {
    console.error('Ошибка при загрузке гайда:', error)
  }
}

export async function buyGuide(guideId, personId) {
  try {
    const response = await axiosInstance.post(
      'guides/purchase',
      { guideId, personId },
      {
        headers: { ...getAuthHeaders(), 'Content-Type': 'application/x-www-form-urlencoded' }
      }
    )

    const data = response.data

    return data
  } catch (error) {
    console.error('Ошибка при покупке гайда:', error.response?.data || error.message)
    throw error
  }
}

export async function searchGuides(searchTerm) {
  try {
    const response = await axiosInstance.get('guides/search', {
      params: { name: searchTerm },
      headers: getAuthHeaders()
    })

    const data = response.data

    return data
  } catch (error) {
    console.error('Error searching guides:', error)
    throw error
  }
}

export async function getProfileInfo() {
  try {
    const response = await axiosInstance.get('user-profile/profile', {
      headers: getAuthHeaders()
    })

    const data = response.data

    return data
  } catch (error) {
    console.error('Ошибка при загрузке задач:', error)
  }
}

export async function uploadAvatar(formData) {
  try {
    const response = await axiosInstance.post('user-profile/upload-photo', formData, {
      headers: { ...getAuthHeaders(), 'Content-Type': 'multipart/form-data' }
    })

    return response
  } catch (error) {
    console.error('Ошибка при загрузке аватара:', error)
  }
}

export async function saveDescription(description) {
  try {
    const response = await axiosInstance.post('user-profile/update-description', {
      headers: getAuthHeaders(),
      description
    })

    return response
  } catch (error) {
    console.error('Ошибка при обновлении описания профиля:', error)
  }
}

export async function saveProfile(info) {
  try {
    const response = await axiosInstance.patch('user-profile/update', {
      name: info.name,
      description: info.description,
      linkName: info.linkName,
      linkUrl: info.linkUrl
    })

    return response
  } catch (error) {
    console.error('Error updating profile:', error)
  }
}

export async function createGuide(formData) {
  try {
    const response = await axiosInstance.post('guides/create', formData, {
      headers: { ...getAuthHeaders(), 'Content-Type': 'multipart/form-data' }
    })

    return response
  } catch (error) {
    console.error('Ошибка при создании гайда:', error)
  }
}
