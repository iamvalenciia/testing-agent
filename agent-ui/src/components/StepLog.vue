<template>
  <div class="steps-container" :class="{ 'dark-mode': isDark }" ref="container">
    <transition-group name="list" tag="div" class="steps-list">
      <div 
        v-for="(step, index) in reversedSteps" 
        :key="step.step_number || (steps.length - index)"
        class="step-card"
        :class="{'latest': index === 0}"
      >
        <div class="step-content">
          <div class="step-header">
             <span class="step-num">#{{ step.step_number || (steps.length - index) }}</span>
             <span class="action-badge">{{ step.action_type || 'ACTION' }}</span>
          </div>
            
          <!-- Screenshot thumbnail is the main content now -->
          <div v-if="step.screenshot" class="screenshot-thumb" @click="$emit('view-image', step.screenshot)">
            <img :src="step.screenshot" alt="Step Screenshot" />
            <div class="overlay">VIEW</div>
          </div>
          <!-- Fallback if no screenshot -->
          <div v-else class="screenshot-thumb" style="display:flex;align-items:center;justify-content:center;background:#222;">
             <span style="font-size:0.6rem;color:#666;">NO IMAGE</span>
          </div>
        </div>
      </div>
    </transition-group>
    
    <div v-if="steps.length === 0" class="empty-state">
      <span class="blink">_AWAITING COMMANDS</span>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch, nextTick } from 'vue';

const props = defineProps({
  steps: {
    type: Array,
    default: () => []
  },
  isDark: {
    type: Boolean,
    default: true
  }
});

defineEmits(['view-image']);

const container = ref(null);

// Reverse steps so newest appears first (on the left)
const reversedSteps = computed(() => [...props.steps].reverse());

// Auto-scroll to the left (start) when new steps are added - so user sees newest first
watch(() => props.steps.length, async () => {
  await nextTick();
  if (container.value) {
    container.value.scrollLeft = 0; // Scroll to leftmost position (newest)
  }
});

function formatTime(ts) {
  if (!ts) return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  return ts;
}

function truncate(val, len = 50) {
  const str = String(val);
  return str.length > len ? str.substring(0, len) + '...' : str;
}
</script>

<style scoped>
/* Horizontal Carousel Styles */
.steps-container {
  display: flex;
  flex-direction: row;
  overflow-x: auto;
  overflow-y: hidden;
  height: 100%;
  padding: 0.5rem;
  gap: 0.75rem;
  background: var(--bg-primary);
  border-top: 1px solid var(--border-color);
  align-items: center;
}

.steps-list {
  display: contents; /* Let children partake in flex container */
}

.step-card {
  flex: 0 0 160px;
  height: 140px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  position: relative;
  transition: all 0.2s ease;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.step-card:hover {
  transform: translateY(-2px);
  border-color: var(--text-primary);
  box-shadow: 0 4px 12px rgba(0,0,0,0.2);
}

.step-card.latest {
  border-color: var(--success);
}

/* Compact Content for Carousel */
.step-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.step-header {
  position: absolute;
  top: 0.5rem;
  left: 0.5rem;
  right: 0.5rem;
  z-index: 2;
  display: flex;
  justify-content: space-between;
  margin: 0;
}

.step-num {
  font-size: 0.6rem;
  background: rgba(0,0,0,0.7);
  color: white;
  padding: 2px 6px;
  border-radius: 4px;
  backdrop-filter: blur(4px);
  font-family: 'JetBrains Mono', monospace;
}

.action-badge {
  font-size: 0.55rem;
  padding: 2px 6px;
  background: rgba(0,0,0,0.7);
  color: white;
  border-radius: 4px;
  backdrop-filter: blur(4px);
  border: none;
  max-width: 100px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Image takes full space */
.screenshot-thumb {
  width: 100%;
  height: 100%;
  margin: 0;
  border: none;
  border-radius: 0;
}

.screenshot-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  filter: none;
  transition: filter 0.3s ease;
}

/* Dark Mode: Reduce brightness for night viewing (only affects display, not downloads) */
.steps-container.dark-mode .screenshot-thumb img {
  filter: brightness(0.6) saturate(0.6);
}

.steps-container.dark-mode .screenshot-thumb:hover img {
  filter: brightness(0.9) saturate(1); /* Slightly brighter on hover */
}

.step-details p {
  display: none; /* Hide details in carousel */
}

.time, .code-block, .reasoning {
  display: none;
}

/* Empty State */
.empty-state {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
