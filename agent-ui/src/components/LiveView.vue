<template>
  <div class="live-view-container">
    <!-- Scanning Line Effect -->
    <div class="scanner-line"></div>
    
    <!-- Main Viewport -->
    <div class="viewport" :class="{ 'has-image': screenshot }">
      <img 
        v-if="screenshot" 
        :src="screenshot" 
        alt="Live Browser View"
        class="screenshot-image"
      />
      
      <!-- Empty State -->
      <div v-else class="empty-viewport">
        <div class="grid-overlay"></div>
        <div class="center-icon">
          <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round">
            <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>
            <line x1="8" y1="21" x2="16" y2="21"></line>
            <line x1="12" y1="17" x2="12" y2="21"></line>
          </svg>
          <span class="label">VIEWPORT STANDBY</span>
        </div>
      </div>
    </div>

    <!-- Status Bar -->
    <div class="status-bar">
      <div class="status-item">
        <span class="status-dot" :class="statusClass"></span>
        <span class="status-text">{{ statusLabel }}</span>
      </div>
      <div class="status-item" v-if="screenshot">
        <span class="meta">LIVE FEED</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  screenshot: {
    type: String,
    default: null
  },
  status: {
    type: String,
    default: 'idle'
  },
  isDark: {
    type: Boolean,
    default: true
  }
});

const statusClass = computed(() => ({
  'running': props.status === 'running' || props.status === 'starting',
  'idle': props.status === 'idle',
  'error': props.status === 'error'
}));

const statusLabel = computed(() => {
  if (props.status === 'running' || props.status === 'starting') return 'EXECUTING';
  if (props.status === 'error') return 'ERROR';
  return 'READY';
});
</script>

<style scoped>
.live-view-container {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--bg-primary);
  overflow: hidden;
}

.scanner-line {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 2px;
  background: linear-gradient(90deg, transparent, var(--text-primary), transparent);
  opacity: 0.3;
  animation: scan 4s linear infinite;
  z-index: 20;
  pointer-events: none;
}

@keyframes scan {
  0% { top: 0%; opacity: 0; }
  10% { opacity: 0.4; }
  90% { opacity: 0.4; }
  100% { top: 100%; opacity: 0; }
}

.viewport {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
}

.screenshot-image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  border-radius: 4px;
}

.empty-viewport {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}

.grid-overlay {
  position: absolute;
  inset: 0;
  background-image: 
    linear-gradient(var(--border-color) 1px, transparent 1px),
    linear-gradient(90deg, var(--border-color) 1px, transparent 1px);
  background-size: 40px 40px;
  opacity: 0.3;
  animation: gridPulse 5s ease-in-out infinite;
}

@keyframes gridPulse {
  0%, 100% { opacity: 0.2; }
  50% { opacity: 0.4; }
}

.center-icon {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
  color: var(--text-muted);
  z-index: 1;
}

.center-icon .label {
  font-size: 0.7rem;
  letter-spacing: 3px;
  font-family: 'JetBrains Mono', monospace;
}

.status-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem 1rem;
  background: var(--bg-secondary);
  border-top: 1px solid var(--border-color);
  font-size: 0.65rem;
  font-family: 'JetBrains Mono', monospace;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-muted);
}

.status-dot.running {
  background: var(--text-primary);
  animation: blink 1s infinite;
}

.status-dot.idle {
  background: var(--success);
}

.status-dot.error {
  background: var(--danger);
}

@keyframes blink {
  50% { opacity: 0.5; }
}

.status-text {
  color: var(--text-secondary);
}

.meta {
  color: var(--text-muted);
}
</style>
