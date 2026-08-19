import axios from 'axios'

const API = process.env.VUE_APP_API_URL

const axiosInstance = axios.create({
  baseURL: API,
  headers: {
    'Content-Type': 'application/json'
  }
})

export default axiosInstance
