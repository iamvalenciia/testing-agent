<template>
  <div
    class="step-card"
    :class="[statusClass, { 'active': isActive, 'clickable': clickable }]"
    @click="handleClick"
  >
    <!-- Status Indicator -->
    <div class="status-indicator">
      <div class="status-dot" :class="statusClass"></div>
      <span class="step-number">Step {{ step.step_id }}</span>
    </div>

    <!-- Action Info -->
    <div class="action-info">
      <span class="action-type">{{ step.action }}</span>
      <span v-if="step.target_description" class="target-desc">
        {{ truncate(step.target_description, 40) }}
      </span>
      <span v-else-if="step.target" class="target-url">
        {{ truncate(step.target, 40) }}
      </span>
    </div>

    <!-- Expected Visual -->
    <div class="expected-visual">
      <span class="label">Expected:</span>
      <span class="value">{{ truncate(step.expected_visual, 60) }}</span>
    </div>

    <!-- Execution Result (when executed) -->
    <div v-if="result" class="execution-result">
      <div v-if="result.status === 'pass'" class="result-pass">
        PASS
        <span v-if="result.evidence?.visual_match_confidence" class="confidence">
          ({{ (result.evidence.visual_match_confidence * 100).toFixed(0) }}%)
        </span>
      </div>
      <div v-else-if="result.status === 'fail'" class="result-fail">
        FAIL
        <span v-if="result.error_message" class="error-msg">
          {{ truncate(result.error_message, 50) }}
        </span>
      </div>
      <div v-else-if="result.status === 'running'" class="result-running">
        <span class="spinner"></span>
        Running...
      </div>
      <div v-else-if="result.status === 'skipped'" class="result-skipped">
        SKIPPED
      </div>
    </div>

    <!-- Retry Count -->
    <div v-if="result?.retry_count > 0" class="retry-info">
      Retries: {{ result.retry_count }}
    </div>

    <!-- Screenshot Preview (if available) -->
    <div
      v-if="screenshot"
      class="screenshot-preview"
      @click.stop="$emit('view-screenshot', screenshot)"
    >
      <img :src="'data:image/png;base64,' + screenshot" alt="Step screenshot" />
      <div class="overlay">VIEW</div>
    </div>
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

const statusClass = computed(() => {
  const status = props.result?.status || props.status;
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
  padding: 12px;
  min-width: 280px;
  max-width: 320px;
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
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.step-card.active {
  border-color: var(--primary, #4ecdc4);
  box-shadow: 0 0 0 2px rgba(78, 205, 196, 0.3);
}

/* Status colors */
.step-card.pending {
  border-left: 3px solid #666;
}

.step-card.running {
  border-left: 3px solid #f0ad4e;
  animation: pulse 1.5s infinite;
}

.step-card.pass {
  border-left: 3px solid #5cb85c;
}

.step-card.fail {
  border-left: 3px solid #d9534f;
}

.step-card.skipped {
  border-left: 3px solid #777;
  opacity: 0.7;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.8; }
}

/* Status Indicator */
.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #666;
}

.status-dot.pending { background: #666; }
.status-dot.running { background: #f0ad4e; animation: blink 1s infinite; }
.status-dot.pass { background: #5cb85c; }
.status-dot.fail { background: #d9534f; }
.status-dot.skipped { background: #777; }

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.step-number {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary, #999);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* Action Info */
.action-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.action-type {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-primary, #fff);
  text-transform: uppercase;
  background: var(--bg-secondary, #252540);
  padding: 4px 8px;
  border-radius: 4px;
  display: inline-block;
  width: fit-content;
}

.target-desc, .target-url {
  font-size: 0.8rem;
  color: var(--text-secondary, #aaa);
  font-family: 'JetBrains Mono', monospace;
}

/* Expected Visual */
.expected-visual {
  font-size: 0.75rem;
  color: var(--text-tertiary, #888);
  border-top: 1px solid var(--border-color, #333);
  padding-top: 8px;
}

.expected-visual .label {
  color: var(--text-secondary, #999);
  margin-right: 4px;
}

.expected-visual .value {
  font-style: italic;
}

/* Execution Result */
.execution-result {
  margin-top: 4px;
}

.result-pass {
  color: #5cb85c;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
}

.result-fail {
  color: #d9534f;
  font-weight: 600;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.result-running {
  color: #f0ad4e;
  display: flex;
  align-items: center;
  gap: 8px;
}

.result-skipped {
  color: #777;
  font-style: italic;
}

.confidence {
  font-weight: normal;
  font-size: 0.8rem;
  color: var(--text-secondary, #999);
}

.error-msg {
  font-size: 0.75rem;
  font-weight: normal;
  color: var(--text-secondary, #bbb);
}

/* Spinner */
.spinner {
  width: 14px;
  height: 14px;
  border: 2px solid #f0ad4e;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Retry Info */
.retry-info {
  font-size: 0.7rem;
  color: #f0ad4e;
}

/* Screenshot Preview */
.screenshot-preview {
  margin-top: 8px;
  position: relative;
  height: 80px;
  border-radius: 4px;
  overflow: hidden;
  cursor: pointer;
}

.screenshot-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  filter: brightness(0.7);
  transition: filter 0.2s ease;
}

.screenshot-preview:hover img {
  filter: brightness(1);
}

.screenshot-preview .overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.5);
  color: white;
  font-size: 0.7rem;
  font-weight: 600;
  opacity: 0;
  transition: opacity 0.2s ease;
}

.screenshot-preview:hover .overlay {
  opacity: 1;
}
</style>
