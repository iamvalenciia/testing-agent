/**
 * Authentication Composable for Google OAuth
 * 
 * Handles:
 * - Google Sign-In integration
 * - Session token management (localStorage)
 * - User state management
 * - Auth verification on app load
 */
import { ref, computed, readonly } from 'vue'

// Backend API URL
const API_URL = 'http://localhost:8000'

// State
const user = ref(null)
const token = ref(null)
const isLoading = ref(false)
const error = ref(null)

// Computed
const isAuthenticated = computed(() => !!token.value && !!user.value)

/**
 * Initialize auth state from localStorage
 */
function initAuth() {
    const storedToken = localStorage.getItem('auth_token')
    const storedUser = localStorage.getItem('auth_user')
    const expiry = localStorage.getItem('auth_expiry')

    if (storedToken && storedUser && expiry) {
        // Check if token is expired
        if (new Date(expiry) > new Date()) {
            token.value = storedToken
            try {
                user.value = JSON.parse(storedUser)
            } catch {
                clearAuth()
            }
        } else {
            // Token expired, clear storage
            clearAuth()
        }
    }
}

/**
 * Clear all auth data
 */
function clearAuth() {
    token.value = null
    user.value = null
    error.value = null
    localStorage.removeItem('auth_token')
    localStorage.removeItem('auth_user')
    localStorage.removeItem('auth_expiry')
}

/**
 * Process Google credential and authenticate with backend
 * @param {string} credential - Google ID token
 */
async function login(credential) {
    isLoading.value = true
    error.value = null

    try {
        const response = await fetch(`${API_URL}/auth/google`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ id_token: credential }),
        })

        if (!response.ok) {
            const data = await response.json()
            throw new Error(data.detail || 'Authentication failed')
        }

        const data = await response.json()

        // Store token and user
        token.value = data.token
        user.value = data.user

        // Calculate expiry (30 days from now)
        const expiry = new Date()
        expiry.setDate(expiry.getDate() + 30)

        // Persist to localStorage
        localStorage.setItem('auth_token', data.token)
        localStorage.setItem('auth_user', JSON.stringify(data.user))
        localStorage.setItem('auth_expiry', expiry.toISOString())

        console.log('[AUTH] Login successful:', data.user.email)

        return true
    } catch (err) {
        console.error('[AUTH] Login failed:', err)
        error.value = err.message
        clearAuth()
        return false
    } finally {
        isLoading.value = false
    }
}

/**
 * Verify current token with backend
 */
async function verifyAuth() {
    if (!token.value) {
        return false
    }

    isLoading.value = true

    try {
        const response = await fetch(`${API_URL}/auth/verify`, {
            headers: {
                'Authorization': `Bearer ${token.value}`,
            },
        })

        if (!response.ok) {
            throw new Error('Token verification failed')
        }

        const data = await response.json()
        user.value = data.user

        return true
    } catch (err) {
        console.warn('[AUTH] Token verification failed:', err)
        clearAuth()
        return false
    } finally {
        isLoading.value = false
    }
}

/**
 * Logout user
 */
async function logout() {
    isLoading.value = true

    try {
        // Notify backend (optional, for logging)
        if (token.value) {
            await fetch(`${API_URL}/auth/logout`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token.value}`,
                },
            }).catch(() => { })
        }
    } finally {
        clearAuth()
        isLoading.value = false
    }
}

/**
 * Get authorization header for API calls
 */
function getAuthHeader() {
    return token.value ? { 'Authorization': `Bearer ${token.value}` } : {}
}

/**
 * Get token for WebSocket connection
 */
function getToken() {
    return token.value
}

/**
 * Composable export
 */
export function useAuth() {
    // Initialize auth on first use
    if (!token.value && !user.value) {
        initAuth()
    }

    return {
        // State (readonly)
        user: readonly(user),
        token: readonly(token),
        isLoading: readonly(isLoading),
        error: readonly(error),
        isAuthenticated,

        // Actions
        login,
        logout,
        verifyAuth,
        initAuth,
        clearAuth,

        // Utilities
        getAuthHeader,
        getToken,
    }
}
