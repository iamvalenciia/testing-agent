<template>
  <div class="login-container" :class="{ 'light-mode': !uiStore.isDark }">
    <!-- Reuse the same dynamic background as the agent -->
    <Background3D :is-dark="uiStore.isDark" />
    
    <!-- Login Card -->
    <div class="login-card glass-panel">
      <!-- Header -->
      <div class="login-header">
        <div class="login-logo">
          <span class="logo-icon">🤖</span>
        </div>
        <h1 class="login-title">Configuration Specialist Agent</h1>
        <p class="login-subtitle">Powered by AI</p>
      </div>

      <!-- Error Message -->
      <div v-if="authStore.error" class="error-message">
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/>
          <line x1="15" y1="9" x2="9" y2="15"/>
          <line x1="9" y1="9" x2="15" y2="15"/>
        </svg>
        <span>{{ authStore.error }}</span>
      </div>

      <!-- Google Sign-In Button -->
      <div class="login-actions">
        <button 
          class="google-signin-btn"
          @click="initGoogleSignIn"
          :disabled="authStore.isLoading"
        >
          <span v-if="authStore.isLoading" class="loading-spinner"></span>
          <template v-else>
            <svg class="google-icon" viewBox="0 0 24 24" width="20" height="20">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
            </svg>
            Sign in with Google
          </template>
        </button>
      </div>

      <!-- Footer -->
      <div class="login-footer">
        <p>Authorized employees only</p>
      </div>
    </div>

    <!-- Theme Toggle (bottom right) -->
    <button 
      class="theme-toggle"
      @click="uiStore.toggleTheme"
      :title="uiStore.isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode'"
    >
      <svg v-if="uiStore.isDark" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="5"></circle>
        <line x1="12" y1="1" x2="12" y2="3"></line>
        <line x1="12" y1="21" x2="12" y2="23"></line>
        <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
        <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
        <line x1="1" y1="12" x2="3" y2="12"></line>
        <line x1="21" y1="12" x2="23" y2="12"></line>
        <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
        <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
      </svg>
      <svg v-else xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
      </svg>
    </button>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import Background3D from '../components/Background3D.vue'
import { useAuthStore } from '../stores/auth'
import { useUiStore } from '../stores/ui'

const router = useRouter()
const authStore = useAuthStore()
const uiStore = useUiStore()

// Google Client ID from environment (injected via Vite)
const GOOGLE_CLIENT_ID = '1064806089838-m2o98dq97hha911j7ugl28p2gf367gnc.apps.googleusercontent.com'

// Clear any previous errors on mount
onMounted(() => {
  authStore.clearAuth()
})

/**
 * Initialize Google Sign-In and handle callback
 */
function initGoogleSignIn() {
  if (!window.google) {
    console.error('[AUTH] Google Identity Services not loaded')
    return
  }
  
  if (!GOOGLE_CLIENT_ID) {
    console.error('[AUTH] GOOGLE_CLIENT_ID not configured')
    return
  }

  // Initialize Google Sign-In
  window.google.accounts.id.initialize({
    client_id: GOOGLE_CLIENT_ID,
    callback: handleGoogleCallback,
    auto_select: false,
    cancel_on_tap_outside: true,
  })
  
  // Show the One Tap prompt or Popup
  window.google.accounts.id.prompt((notification) => {
    if (notification.isNotDisplayed() || notification.isSkippedMoment()) {
      // Fallback to button popup if One Tap not available
      showGooglePopup()
    }
  })
}

/**
 * Show Google popup sign-in
 */
function showGooglePopup() {
  window.google.accounts.id.renderButton(
    document.createElement('div'),
    { theme: 'outline', size: 'large' }
  )
  
  // Use prompt with user gesture
  window.google.accounts.oauth2.initTokenClient({
    client_id: GOOGLE_CLIENT_ID,
    scope: 'email profile',
    callback: handleGoogleCallback,
  }).requestAccessToken()
}

/**
 * Handle Google callback
 */
async function handleGoogleCallback(response) {
  if (response.credential) {
    const success = await authStore.login(response.credential)
    if (success) {
      router.push({ name: 'agent' })
    }
  } else if (response.error) {
    console.error('[AUTH] Google sign-in error:', response.error)
  }
}
</script>

<style scoped>
.login-container {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

/* Glass Panel - matches agent UI style */
.login-card {
  background: rgba(20, 20, 25, 0.85);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 20px;
  padding: 48px 40px;
  width: 100%;
  max-width: 400px;
  box-shadow: 
    0 25px 50px -12px rgba(0, 0, 0, 0.5),
    0 0 0 1px rgba(255, 255, 255, 0.05);
  position: relative;
  z-index: 10;
  text-align: center;
}

.light-mode .login-card {
  background: rgba(255, 255, 255, 0.9);
  border-color: rgba(0, 0, 0, 0.1);
  box-shadow: 
    0 25px 50px -12px rgba(0, 0, 0, 0.15),
    0 0 0 1px rgba(0, 0, 0, 0.05);
}

/* Header */
.login-header {
  margin-bottom: 32px;
}

.login-logo {
  width: 72px;
  height: 72px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 20px;
  box-shadow: 0 10px 30px rgba(102, 126, 234, 0.3);
}

.logo-icon {
  font-size: 36px;
}

.login-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: #fff;
  margin: 0 0 8px;
  letter-spacing: -0.02em;
}

.light-mode .login-title {
  color: #1a1a1a;
}

.login-subtitle {
  font-size: 0.875rem;
  color: rgba(255, 255, 255, 0.5);
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.light-mode .login-subtitle {
  color: rgba(0, 0, 0, 0.4);
}

/* Error Message */
.error-message {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px 16px;
  background: rgba(239, 68, 68, 0.15);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 10px;
  color: #ef4444;
  font-size: 0.875rem;
  margin-bottom: 24px;
}

/* Google Sign-In Button */
.login-actions {
  margin: 24px 0;
}

.google-signin-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  width: 100%;
  padding: 14px 24px;
  background: #fff;
  border: none;
  border-radius: 12px;
  font-size: 1rem;
  font-weight: 600;
  color: #1a1a1a;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 
    0 2px 8px rgba(0, 0, 0, 0.1),
    0 0 0 1px rgba(0, 0, 0, 0.05);
}

.google-signin-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 
    0 8px 20px rgba(0, 0, 0, 0.15),
    0 0 0 1px rgba(0, 0, 0, 0.08);
}

.google-signin-btn:active:not(:disabled) {
  transform: translateY(0);
}

.google-signin-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.google-icon {
  flex-shrink: 0;
}

/* Loading Spinner */
.loading-spinner {
  width: 20px;
  height: 20px;
  border: 2px solid #e5e5e5;
  border-top-color: #667eea;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Footer */
.login-footer {
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.light-mode .login-footer {
  border-top-color: rgba(0, 0, 0, 0.1);
}

.login-footer p {
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.4);
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.light-mode .login-footer p {
  color: rgba(0, 0, 0, 0.4);
}

/* Theme Toggle */
.theme-toggle {
  position: fixed;
  bottom: 24px;
  right: 24px;
  width: 44px;
  height: 44px;
  background: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
  color: rgba(255, 255, 255, 0.7);
  z-index: 100;
}

.light-mode .theme-toggle {
  background: rgba(0, 0, 0, 0.05);
  border-color: rgba(0, 0, 0, 0.1);
  color: rgba(0, 0, 0, 0.6);
}

.theme-toggle:hover {
  background: rgba(255, 255, 255, 0.2);
  transform: translateY(-2px);
}

.light-mode .theme-toggle:hover {
  background: rgba(0, 0, 0, 0.1);
}
</style>
