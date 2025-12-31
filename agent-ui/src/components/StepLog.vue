<template>
  <div class="steps-container" ref="container">
    <transition-group name="list" tag="div" class="steps-list">
      <div 
        v-for="(step, index) in reversedSteps" 
        :key="step.step_number || index"
        class="step-card"
        :class="{'latest': index === 0}"
      >
        <div class="step-indicator">
          <span class="step-num">#{{ step.step_number || index + 1 }}</span>
          <div class="pulse-ring" v-if="index === 0"></div>
        </div>
        
        <div class="step-content">
          <div class="step-header">
            <span class="action-badge">{{ step.action_type || step.name || 'ACTION' }}</span>
            <span class="time">{{ formatTime(step.timestamp) }}</span>
          </div>
          
          <div class="step-details">
            <div v-if="step.args && Object.keys(step.args).length > 0" class="code-block">
              <span v-for="(val, key) in step.args" :key="key" class="arg-item">
                <span class="key">{{ key }}:</span> <span class="val">{{ truncate(val) }}</span>
              </span>
            </div>
            <p v-if="step.reasoning" class="reasoning">
              "{{ step.reasoning }}"
            </p>
            
            <!-- Screenshot thumbnail -->
            <div v-if="step.screenshot" class="screenshot-thumb" @click="$emit('view-image', step.screenshot)">
              <img :src="step.screenshot" alt="Step Screenshot" />
              <div class="overlay">VIEW</div>
            </div>
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
import { computed } from 'vue';

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

const reversedSteps = computed(() => {
  return [...props.steps].reverse();
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
.steps-container {
  overflow-y: auto;
  height: 100%;
  padding-right: 5px;
}

.steps-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.step-card {
  background: var(--bg-tertiary);
  border-left: 2px solid var(--border-color);
  padding: 0.75rem 1rem;
  border-radius: 0 8px 8px 0;
  position: relative;
  transition: all 0.3s ease;
}

.step-card.latest {
  background: var(--bg-secondary);
  border-left: 2px solid var(--text-primary);
}

.step-indicator {
  position: absolute;
  left: -10px;
  top: 0.75rem;
}

.step-num {
  font-size: 0.6rem;
  color: var(--text-muted);
  font-family: 'JetBrains Mono', monospace;
}

.pulse-ring {
  position: absolute;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-primary);
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0% { transform: scale(1); opacity: 1; }
  100% { transform: scale(2); opacity: 0; }
}

.step-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.5rem;
  align-items: center;
}

.action-badge {
  background: var(--bg-primary);
  color: var(--text-secondary);
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.65rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 1px;
  border: 1px solid var(--border-color);
}

.time {
  font-size: 0.6rem;
  color: var(--text-muted);
  font-family: 'JetBrains Mono', monospace;
}

.code-block {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 0.7rem;
  background: var(--bg-primary);
  padding: 0.5rem;
  border-radius: 4px;
  margin-top: 0.5rem;
  border: 1px solid var(--border-color);
}

.arg-item {
  display: block;
  margin-bottom: 2px;
}

.key { color: var(--text-secondary); }
.val { color: var(--text-primary); }

.reasoning {
  font-style: italic;
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-top: 0.5rem;
  border-left: 2px solid var(--border-color);
  padding-left: 0.5rem;
  margin-bottom: 0;
}

.screenshot-thumb {
  margin-top: 0.5rem;
  position: relative;
  display: inline-block;
  cursor: pointer;
  border-radius: 4px;
  overflow: hidden;
  border: 1px solid var(--border-color);
}

.screenshot-thumb img {
  height: 50px;
  width: auto;
  display: block;
  transition: transform 0.3s;
  filter: grayscale(0.3);
}

.screenshot-thumb:hover img {
  transform: scale(1.05);
  filter: grayscale(0);
}

.screenshot-thumb .overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.55rem;
  font-weight: bold;
  color: white;
  opacity: 0;
  transition: opacity 0.3s;
  letter-spacing: 1px;
}

.screenshot-thumb:hover .overlay {
  opacity: 1;
}

.empty-state {
  text-align: center;
  color: var(--text-muted);
  margin-top: 2rem;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
}

.blink {
  animation: blink 1s infinite;
}

@keyframes blink {
  50% { opacity: 0; }
}

/* Vue Transition Animations */
.list-enter-active,
.list-leave-active {
  transition: all 0.4s ease;
}
.list-enter-from {
  opacity: 0;
  transform: translateX(15px);
}
.list-leave-to {
  opacity: 0;
  transform: translateX(-15px);
}
</style>
