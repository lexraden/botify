export function formatTimeAgo(dateArray) {
  const [year, month, day, hour, minute, second] = dateArray
  const guideDate = new Date(year, month - 1, day, hour, minute, second)
  const now = new Date()
  const diffInSeconds = Math.floor((now - guideDate) / 1000)

  const secondsInMinute = 60
  const secondsInHour = 60 * 60
  const secondsInDay = 60 * 60 * 24
  const secondsInMonth = 60 * 60 * 24 * 30
  const secondsInYear = 60 * 60 * 24 * 365

  if (diffInSeconds < secondsInMinute) {
    return `${diffInSeconds} seconds ago`
  } else if (diffInSeconds < secondsInHour) {
    const minutes = Math.floor(diffInSeconds / secondsInMinute)
    return `${minutes} minute${minutes > 1 ? 's' : ''} ago`
  } else if (diffInSeconds < secondsInDay) {
    const hours = Math.floor(diffInSeconds / secondsInHour)
    return `${hours} hour${hours > 1 ? 's' : ''} ago`
  } else if (diffInSeconds < secondsInMonth) {
    const days = Math.floor(diffInSeconds / secondsInDay)
    return `${days} day${days > 1 ? 's' : ''} ago`
  } else if (diffInSeconds < secondsInYear) {
    const months = Math.floor(diffInSeconds / secondsInMonth)
    return `${months} month${months > 1 ? 's' : ''} ago`
  } else {
    const years = Math.floor(diffInSeconds / secondsInYear)
    return `${years} year${years > 1 ? 's' : ''} ago`
  }
}

export function formatDaysAgo(dateArray) {
  const [year, month, day] = dateArray
  const guideDate = new Date(year, month - 1, day)
  const now = new Date()
  const diffInDays = Math.floor((now - guideDate) / (1000 * 60 * 60 * 24))

  if (diffInDays < 1) return 'Сегодня'
  if (diffInDays === 1) return 'Вчера'
  return `${diffInDays} дней назад`
}
