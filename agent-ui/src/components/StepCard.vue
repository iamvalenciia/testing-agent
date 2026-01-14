<template>
  <div
    class="step-card"
    :class="[statusClass, { 'active': isActive, 'clickable': clickable }]"
    @click="handleClick"
  >
    <!-- Header with Step Number and Status Icon -->
    <div class="step-header">
      <div class="step-number-badge">{{ step.step_id }}</div>
      <div class="step-title-area">
        <span class="action-type">{{ step.action.toUpperCase() }}</span>
        <span v-if="step.target_description" class="target-desc">
          {{ truncate(step.target_description, 50) }}
        </span>
        <span v-else-if="step.target" class="target-url">
          {{ truncate(step.target, 50) }}
        </span>
      </div>
      <div class="status-icon">
        <!-- Pass: Green checkmark -->
        <div v-if="currentStatus === 'pass'" class="icon-pass">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
            <polyline points="20 6 9 17 4 12"></polyline>
          </svg>
        </div>
        <!-- Fail: Red X -->
        <div v-else-if="currentStatus === 'fail'" class="icon-fail">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </div>
        <!-- Running: Spinner -->
        <div v-else-if="currentStatus === 'running'" class="icon-running">
          <div class="spinner-ring"></div>
        </div>
        <!-- Skipped: Dash -->
        <div v-else-if="currentStatus === 'skipped'" class="icon-skipped">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
            <line x1="5" y1="12" x2="19" y2="12"></line>
          </svg>
        </div>
        <!-- Pending: Circle -->
        <div v-else class="icon-pending">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"></circle>
          </svg>
        </div>
      </div>
    </div>

    <!-- Expected Visual -->
    <div class="expected-visual">
      <span class="label">Expected:</span>
      <span class="value">{{ truncate(step.expected_visual, 80) }}</span>
    </div>

    <!-- Screenshot Preview (prominent if available) -->
    <div
      v-if="screenshot"
      class="screenshot-preview"
      @click.stop="$emit('view-screenshot', screenshot)"
    >
      <img :src="'data:image/png;base64,' + screenshot" alt="Step screenshot" />
      <div class="screenshot-overlay">
        <span class="view-label">Click to View</span>
      </div>
    </div>

    <!-- Execution Details (when executed) -->
    <div v-if="result" class="execution-details">
      <div v-if="result.status === 'fail' && result.error_message" class="error-message">
        {{ truncate(result.error_message, 100) }}
      </div>
      <div class="execution-meta">
        <span v-if="result.evidence?.visual_match_confidence" class="confidence-badge">
          {{ (result.evidence.visual_match_confidence * 100).toFixed(0) }}% confidence
        </span>
        <span v-if="result.retry_count > 0" class="retry-badge">
          {{ result.retry_count }} {{ result.retry_count === 1 ? 'retry' : 'retries' }}
        </span>
        <span v-if="result.execution_time_ms" class="time-badge">
          {{ formatTime(result.execution_time_ms) }}
        </span>
      </div>
    </div>

    <!-- Play button for step execution -->
    <button
      v-if="clickable && currentStatus !== 'running'"
      class="run-step-btn"
      @click.stop="$emit('run-step', step)"
      title="Run this step"
    >
      <svg viewBox="0 0 24 24" fill="currentColor">
        <polygon points="5 3 19 12 5 21 5 3"></polygon>
      </svg>
    </button>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  step: {
    type: Object,
    required: true
  },
  result: {
    type: Object,
    default: null
  },
  status: {
    type: String,
    default: 'pending' // pending, running, pass, fail, skipped
  },
  isActive: {
    type: Boolean,
    default: false
  },
  clickable: {
    type: Boolean,
    default: false
  },
  screenshot: {
    type: String,
    default: null
  }
});

const emit = defineEmits(['click', 'view-screenshot', 'run-step']);

const currentStatus = computed(() => props.result?.status || props.status);

const statusClass = computed(() => {
  const status = currentStatus.value;
  return {
    'pending': status === 'pending',
    'running': status === 'running',
    'pass': status === 'pass',
    'fail': status === 'fail',
    'skipped': status === 'skipped'
  };
});

function truncate(str, maxLen) {
  if (!str) return '';
  return str.length > maxLen ? str.substring(0, maxLen) + '...' : str;
}

function formatTime(ms) {
  if (!ms) return '';
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}m`;
}

function handleClick() {
  if (props.clickable) {
    emit('click', props.step);
  }
}
</script>

<style scoped>
.step-card {
  background: var(--bg-tertiary, #1a1a2e);
  border: 1px solid var(--border-color, #333);
  border-radius: 8px;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  transition: all 0.2s ease;
  position: relative;
}

.step-card.clickable {
  cursor: pointer;
}

.step-card.clickable:hover {
  border-color: var(--text-secondary, #666);
  background: var(--bg-secondary, #1e1e36);
}

.step-card.active {
  border-color: var(--primary, #4ecdc4);
  box-shadow: 0 0 0 1px rgba(78, 205, 196, 0.3);
}

/* Status colors - left border indicator */
.step-card.pending {
  border-left: 3px solid #666;
}

.step-card.running {
  border-left: 3px solid #f0ad4e;
  animation: cardPulse 1.5s infinite;
}

.step-card.pass {
  border-left: 3px solid #22c55e;
  background: rgba(34, 197, 94, 0.05);
}

.step-card.fail {
  border-left: 3px solid #ef4444;
  background: rgba(239, 68, 68, 0.05);
}

.step-card.skipped {
  border-left: 3px solid #777;
  opacity: 0.6;
}

@keyframes cardPulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(240, 173, 78, 0.4); }
  50% { box-shadow: 0 0 0 2px rgba(240, 173, 78, 0.1); }
}

/* Step Header */
.step-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.step-number-badge {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--bg-secondary, #252540);
  border: 2px solid var(--border-color, #444);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.65rem;
  font-weight: 700;
  color: var(--text-primary, #fff);
  flex-shrink: 0;
}

.step-card.pass .step-number-badge {
  background: #22c55e;
  border-color: #22c55e;
  color: #fff;
}

.step-card.fail .step-number-badge {
  background: #ef4444;
  border-color: #ef4444;
  color: #fff;
}

.step-card.running .step-number-badge {
  border-color: #f0ad4e;
  color: #f0ad4e;
}

.step-title-area {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.action-type {
  font-size: 0.65rem;
  font-weight: 700;
  color: var(--primary, #4ecdc4);
  letter-spacing: 0.3px;
}

.target-desc, .target-url {
  font-size: 0.6rem;
  color: var(--text-secondary, #aaa);
  font-family: 'JetBrains Mono', monospace;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Status Icon */
.status-icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.icon-pass {
  width: 20px;
  height: 20px;
  background: #22c55e;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.icon-pass svg {
  width: 12px;
  height: 12px;
  color: #fff;
}

.icon-fail {
  width: 20px;
  height: 20px;
  background: #ef4444;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.icon-fail svg {
  width: 12px;
  height: 12px;
  color: #fff;
}

.icon-running {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.spinner-ring {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(240, 173, 78, 0.3);
  border-top-color: #f0ad4e;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

.icon-skipped {
  width: 20px;
  height: 20px;
  background: #555;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.icon-skipped svg {
  width: 12px;
  height: 12px;
  color: #999;
}

.icon-pending {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.icon-pending svg {
  width: 16px;
  height: 16px;
  color: #666;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Expected Visual */
.expected-visual {
  font-size: 0.6rem;
  color: var(--text-tertiary, #888);
  padding: 6px 8px;
  background: var(--bg-secondary, #151528);
  border-radius: 4px;
  line-height: 1.3;
}

.expected-visual .label {
  color: var(--text-secondary, #999);
  font-weight: 600;
  margin-right: 4px;
}

.expected-visual .value {
  color: var(--text-primary, #ccc);
}

/* Screenshot Preview */
.screenshot-preview {
  position: relative;
  height: 70px;
  border-radius: 4px;
  overflow: hidden;
  cursor: pointer;
  border: 1px solid var(--border-color, #333);
}

.screenshot-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: all 0.2s ease;
}

.screenshot-preview:hover img {
  transform: scale(1.02);
}

.screenshot-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.6);
  opacity: 0;
  transition: opacity 0.2s ease;
}

.screenshot-preview:hover .screenshot-overlay {
  opacity: 1;
}

.view-label {
  color: white;
  font-size: 0.6rem;
  font-weight: 600;
  padding: 4px 8px;
  background: rgba(78, 205, 196, 0.8);
  border-radius: 3px;
}

/* Execution Details */
.execution-details {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.error-message {
  font-size: 0.55rem;
  color: #ef4444;
  background: rgba(239, 68, 68, 0.1);
  padding: 4px 6px;
  border-radius: 3px;
  border-left: 2px solid #ef4444;
}

.execution-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.confidence-badge,
.retry-badge,
.time-badge {
  font-size: 0.55rem;
  padding: 2px 5px;
  border-radius: 3px;
  background: var(--bg-secondary, #252540);
  color: var(--text-secondary, #999);
}

.retry-badge {
  color: #f0ad4e;
  background: rgba(240, 173, 78, 0.15);
}

/* Run Step Button */
.run-step-btn {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 22px;
  height: 22px;
  border: none;
  border-radius: 50%;
  background: var(--primary, #4ecdc4);
  color: #000;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: all 0.2s ease;
}

.step-card:hover .run-step-btn {
  opacity: 1;
}

.run-step-btn:hover {
  transform: scale(1.1);
  background: #3dbdb5;
}

.run-step-btn svg {
  width: 10px;
  height: 10px;
}
</style>
