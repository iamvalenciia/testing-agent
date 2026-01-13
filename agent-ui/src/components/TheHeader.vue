<template>
  <header class="glass-header">
    <div class="logo-area">
      <span class="status-dot" :class="connectionStatusClass"></span>
      <h1>Configuration Specialist Agent</h1>
      <div v-if="hammerMetadata?.indexed" class="hammer-info">
        <span class="company-badge">
          🔨 {{ hammerMetadata.company_name }}
          <span class="company-id">({{ hammerMetadata.company_id }})</span>
        </span>
        <span v-if="hammerMetadata.jira_label" class="jira-label">
          🏷️ {{ hammerMetadata.jira_label }}
        </span>
      </div>
      <div v-else-if="hammerMetadata" class="hammer-info no-hammer">
        <span class="no-hammer-badge">📁 No Hammer Indexed</span>
      </div>
    </div>
    <div class="controls">
      <!-- Mode Toggle -->
      <button 
        class="control-btn mode-toggle" 
        @click="$emit('toggle-mode')"
        :class="{ 'production-mode': isProductionMode }"
        :title="isProductionMode ? 'Switch to Training Mode' : 'Switch to Production Mode'"
      >
        <span class="mode-icon">{{ isProductionMode ? '🛡️' : '🎓' }}</span>
        <span class="mode-label">{{ isProductionMode ? 'PRODUCTION' : 'TRAINING' }}</span>
      </button>

      <!-- Hammer Upload Button -->
      <button 
        class="control-btn hammer-btn" 
        @click="$emit('open-hammer')"
        title="Upload/Index Hammer File"
        :disabled="isRunning"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>
        HAMMER
      </button>

      <!-- Theme Toggle -->
      <button 
        class="control-btn icon-btn" 
        @click="$emit('toggle-theme')"
        :title="isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode'"
      >
        <svg v-if="isDark" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
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
        <svg v-else xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
        </svg>
      </button>

      <!-- Close Browser -->
      <button 
        v-if="hasBrowser && !isRunning" 
        class="control-btn icon-btn" 
        @click="$emit('close-browser')"
        title="Close Browser"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
      </button>

      <!-- Save Workflow -->
      <button 
        v-if="hasSteps && !isRunning" 
        class="control-btn" 
        @click="$emit('open-workflow')"
        title="Save Workflow"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
        SAVE
      </button>

      <!-- Report Button -->
      <button 
        v-if="hasSteps && !isRunning" 
        class="control-btn report" 
        @click="$emit('open-report')"
        title="Generate Session Report"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
        REPORT
      </button>

      <!-- Save Success Case -->
      <button 
        v-if="hasSteps && !isRunning" 
        class="control-btn success" 
        @click="$emit('open-success')"
        title="Save Success Case"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
        SUCCESS
      </button>

      <!-- Static Data -->
      <button 
        class="control-btn static" 
        @click="$emit('open-static')"
        title="Save Static Reference Data"
        :disabled="isSaving"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>
        STATIC DATA
      </button>
      
      <!-- End Session -->
      <button 
        v-if="hasSteps" 
        class="control-btn danger" 
        @click="$emit('end-session')"
        title="End Session"
      >
        END
      </button>

      <!-- User Profile -->
      <div v-if="user" class="user-profile">
        <img 
          v-if="user.picture" 
          :src="user.picture" 
          :alt="user.name || 'User'" 
          class="profile-avatar"
          @error="handleAvatarError"
        />
        <span class="profile-name">{{ user.name?.split(' ')[0] }}</span>
        <button 
          class="control-btn logout-btn" 
          @click="$emit('logout')"
          title="Logout"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
            <polyline points="16 17 21 12 16 7"/>
            <line x1="21" y1="12" x2="9" y2="12"/>
          </svg>
        </button>
      </div>
    </div>
  </header>
</template>

<script setup>
defineProps({
  connectionStatusClass: { type: Object, default: () => ({}) },
  isProductionMode: { type: Boolean, default: false },
  isDark: { type: Boolean, default: true },
  isRunning: { type: Boolean, default: false },
  hasBrowser: { type: Boolean, default: false },
  hasSteps: { type: Boolean, default: false },
  isSaving: { type: Boolean, default: false },
  user: { type: Object, default: null },
  hammerMetadata: { type: Object, default: null }
})

defineEmits([
  'toggle-mode',
  'toggle-theme',
  'close-browser',
  'open-workflow',
  'open-report',
  'open-success',
  'open-static',
  'open-hammer',
  'end-session',
  'logout'
])

function handleAvatarError(e) {
  e.target.src = 'data:image/svg+xml,' + encodeURIComponent(`
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40">
      <circle cx="20" cy="20" r="20" fill="#667eea"/>
      <text x="20" y="26" text-anchor="middle" fill="white" font-size="16" font-family="Arial">?</text>
    </svg>
  `)
}
</script>

<style scoped>
/* Hammer metadata styles */
.hammer-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-left: 1rem;
  padding-left: 1rem;
  border-left: 1px solid rgba(255, 255, 255, 0.2);
}

.company-badge {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.25rem 0.5rem;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.2), rgba(118, 75, 162, 0.2));
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--text-primary, #fff);
}

.company-id {
  opacity: 0.7;
  font-size: 0.7rem;
}

.jira-label {
  padding: 0.2rem 0.4rem;
  background: rgba(0, 135, 90, 0.2);
  border-radius: 4px;
  font-size: 0.65rem;
  color: #00d68f;
}

.no-hammer {
  opacity: 0.6;
}

.no-hammer-badge {
  font-size: 0.7rem;
  color: var(--text-secondary, #aaa);
}
</style>

