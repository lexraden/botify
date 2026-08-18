import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Main',
    component: () => import('@/pages/MainPage/MainPage.vue')
  },
  {
    path: '/add',
    component: () => import('@/pages/AddPage/AddPage.vue')
  },
  {
    path: '/guide/:id',
    component: () => import('@/pages/GuidePage/GuidePage.vue')
  },
  {
    path: '/add_form',
    component: () => import('@/pages/AddFormPage/AddFormPage.vue')
  },
  {
    path: '/earn',
    component: () => import('@/pages/ProfilePage/ProfilePage.vue')
  },
  {
    path: '/profile/:reflink',
    component: () => import('@/pages/AnotherProfile/AnotherProfile.vue')
  },
  {
    path: '/edit-profile',
    name: 'EditProfile',
    component: () => import('@/pages/EditProfile/EditProfile.vue')
  },
  {
    path: '/search',
    name: 'SearchPage',
    component: () => import('@/pages/SearchPage/SearchPage.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
