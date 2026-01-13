<template>
  <div class="login-container" :class="{ 'light-mode': !isDark }">
    <!-- Reuse the same dynamic background as the agent -->
    <Background3D :is-dark="isDark" />
    
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
      <div v-if="error" class="error-message">
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/>
          <line x1="15" y1="9" x2="9" y2="15"/>
          <line x1="9" y1="9" x2="15" y2="15"/>
        </svg>
        <span>{{ error }}</span>
      </div>

      <!-- Official Google Sign-In Button Container -->
      <div class="login-actions">
        <div ref="googleButtonRef" class="google-button-container"></div>
        
        <!-- Loading indicator while Google SDK loads -->
        <div v-if="!googleLoaded" class="google-loading">
          <span class="loading-spinner"></span>
          <span>Loading Google Sign-In...</span>
        </div>
      </div>

      <!-- Footer -->
      <div class="login-footer">
        <p>Authorized employees only</p>
      </div>
    </div>

    <!-- Theme Toggle (bottom right) -->
    <button 
      class="theme-toggle"
      @click="toggleTheme"
      :title="isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode'"
    >
      <svg v-if="isDark" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
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
import { ref, onMounted } from 'vue'
import Background3D from './Background3D.vue'
import { useAuth } from '../composables/useAuth'

const emit = defineEmits(['authenticated'])

// Google Client ID (Public - safe to expose)
const GOOGLE_CLIENT_ID = '1064806089838-m2o98dq97hha911j7ugl28p2gf367gnc.apps.googleusercontent.com'

// Refs
const googleButtonRef = ref(null)
const googleLoaded = ref(false)
const isDark = ref(true)

// Auth composable
const { login, isLoading, error, clearAuth } = useAuth()

function toggleTheme() {
  isDark.value = !isDark.value
  localStorage.setItem('theme', isDark.value ? 'dark' : 'light')
}

/**
 * Handle Google callback with credential
 */
async function handleGoogleCallback(response) {
  console.log('[AUTH] Google callback received, credential present:', !!response.credential)
  
  if (response.credential) {
    const success = await login(response.credential)
    if (success) {
      emit('authenticated')
    }
  }
}

/**
 * Initialize Google Sign-In and render official button
 */
function initGoogleSignIn() {
  if (!window.google?.accounts?.id) {
    console.error('[AUTH] Google Identity Services not available')
    return
  }

  // Initialize the client
  window.google.accounts.id.initialize({
    client_id: GOOGLE_CLIENT_ID,
    callback: handleGoogleCallback,
    auto_select: false,
    cancel_on_tap_outside: true,
  })

  // Render the official Google button in our container
  if (googleButtonRef.value) {
    window.google.accounts.id.renderButton(
      googleButtonRef.value,
      {
        type: 'standard',
        theme: isDark.value ? 'filled_black' : 'outline',
        size: 'large',
        width: 300,
        text: 'signin_with',
        shape: 'rectangular',
        logo_alignment: 'left',
      }
    )
    googleLoaded.value = true
    console.log('[AUTH] Google Sign-In button rendered')
  }

  // Also show One Tap if available (optional enhancement)
  window.google.accounts.id.prompt((notification) => {
    console.log('[AUTH] One Tap status:', notification.getMomentType())
  })
}

onMounted(() => {
  // Load theme
  const savedTheme = localStorage.getItem('theme')
  isDark.value = savedTheme !== 'light'
  
  // Clear previous errors
  clearAuth()
  
  // Wait for Google script to load
  const waitForGoogle = setInterval(() => {
    if (window.google?.accounts?.id) {
      clearInterval(waitForGoogle)
      initGoogleSignIn()
    }
  }, 100)
  
  // Timeout after 10 seconds
  setTimeout(() => {
    clearInterval(waitForGoogle)
    if (!googleLoaded.value) {
      console.error('[AUTH] Google Sign-In failed to load after 10 seconds')
    }
  }, 10000)
})
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

/* Google Sign-In Button Container */
.login-actions {
  margin: 24px 0;
  display: flex;
  justify-content: center;
  min-height: 44px;
}

.google-button-container {
  display: flex;
  justify-content: center;
}

.google-loading {
  display: flex;
  align-items: center;
  gap: 10px;
  color: rgba(255, 255, 255, 0.6);
  font-size: 0.875rem;
}

.light-mode .google-loading {
  color: rgba(0, 0, 0, 0.5);
}

/* Loading Spinner */
.loading-spinner {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-top-color: #667eea;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.light-mode .loading-spinner {
  border-color: rgba(0, 0, 0, 0.1);
  border-top-color: #667eea;
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
