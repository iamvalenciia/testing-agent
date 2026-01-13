/**
 * Vue Router Configuration
 * Handles routing between Login and Agent views.
 */
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

// Lazy-load views
const AgentView = () => import('../views/AgentView.vue')
const LoginView = () => import('../views/LoginView.vue')

const routes = [
    {
        path: '/',
        name: 'agent',
        component: AgentView,
        meta: { requiresAuth: true }
    },
    {
        path: '/login',
        name: 'login',
        component: LoginView,
        meta: { guest: true }
    },
]

const router = createRouter({
    history: createWebHistory(),
    routes,
})

// Navigation Guard
router.beforeEach((to, from, next) => {
    const authStore = useAuthStore()
    authStore.initAuth()

    if (to.meta.requiresAuth && !authStore.isAuthenticated) {
        next({ name: 'login' })
    } else if (to.meta.guest && authStore.isAuthenticated) {
        next({ name: 'agent' })
    } else {
        next()
    }
})

export default router
