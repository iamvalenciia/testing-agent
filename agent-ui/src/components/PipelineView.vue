<template>
  <div class="pipeline-container" :class="{ 'dark-mode': isDark }">
    <!-- Pipeline Header -->
    <div class="pipeline-header">
      <div class="test-info">
        <h3 v-if="testPlan">{{ testPlan.test_case_id }}</h3>
        <p v-if="testPlan">{{ testPlan.description }}</p>
      </div>

      <div class="pipeline-controls">
        <button
          v-if="canRunAll"
          class="btn btn-primary"
          @click="$emit('run-all')"
          :disabled="isRunning"
        >
          <span class="icon">&#9654;</span>
          Run All
        </button>

        <button
          v-if="hasFailedSteps && !isRunning"
          class="btn btn-warning"
          @click="$emit('resume')"
        >
          <span class="icon">&#8635;</span>
          Resume
        </button>

        <button
          v-if="isRunning"
          class="btn btn-danger"
          @click="$emit('stop')"
        >
          <span class="icon">&#9632;</span>
          Stop
        </button>
      </div>

      <!-- Progress Bar -->
      <div v-if="testPlan" class="progress-bar">
        <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
        <span class="progress-text">{{ completedSteps }} / {{ totalSteps }}</span>
      </div>
    </div>

    <!-- Pipeline Steps -->
    <div class="pipeline-steps" ref="pipelineRef">
      <div
        v-for="(step, index) in steps"
        :key="step.step_id"
        class="pipeline-step"
      >
        <!-- Connector Line -->
        <div v-if="index > 0" class="connector" :class="getConnectorClass(index)"></div>

        <!-- Step Card -->
        <StepCard
          :step="step"
          :result="getStepResult(step.step_id)"
          :status="getStepStatus(step.step_id)"
          :is-active="currentStepId === step.step_id"
          :clickable="!isRunning"
          :screenshot="getStepScreenshot(step.step_id)"
          @click="handleStepClick"
          @view-screenshot="$emit('view-screenshot', $event)"
        />
      </div>
    </div>

    <!-- Empty State -->
    <div v-if="!testPlan" class="empty-state">
      <div class="empty-icon">&#128203;</div>
      <h4>No Test Plan Loaded</h4>
      <p>Upload a JSON test plan or paste it in the input area to begin.</p>
    </div>

    <!-- Summary Panel (when completed) -->
    <div v-if="executionResult" class="summary-panel">
      <div class="summary-header">
        <h4>Execution Summary</h4>
        <span
          class="overall-status"
          :class="executionResult.overall_status"
        >
          {{ executionResult.overall_status.toUpperCase() }}
        </span>
      </div>

      <div class="summary-stats">
        <div class="stat">
          <span class="stat-value pass">{{ executionResult.passed_steps }}</span>
          <span class="stat-label">Passed</span>
        </div>
        <div class="stat">
          <span class="stat-value fail">{{ executionResult.failed_steps }}</span>
          <span class="stat-label">Failed</span>
        </div>
        <div class="stat">
          <span class="stat-value skip">{{ executionResult.skipped_steps }}</span>
          <span class="stat-label">Skipped</span>
        </div>
        <div class="stat">
          <span class="stat-value time">{{ formatTime(executionResult.total_execution_time_ms) }}</span>
          <span class="stat-label">Duration</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue';
import StepCard from './StepCard.vue';

const props = defineProps({
  testPlan: {
    type: Object,
    default: null
  },
  stepsStatus: {
    type: Object,
    default: () => ({})
  },
  stepsResults: {
    type: Array,
    default: () => []
  },
  currentStepId: {
    type: Number,
    default: null
  },
  isRunning: {
    type: Boolean,
    default: false
  },
  executionResult: {
    type: Object,
    default: null
  },
  screenshots: {
    type: Object,
    default: () => ({})
  },
  isDark: {
    type: Boolean,
    default: true
  }
});

const emit = defineEmits([
  'run-all',
  'run-step',
  'resume',
  'stop',
  'view-screenshot'
]);

const pipelineRef = ref(null);

// Computed
const steps = computed(() => props.testPlan?.steps || []);

const totalSteps = computed(() => steps.value.length);

const completedSteps = computed(() => {
  return Object.values(props.stepsStatus).filter(
    s => s === 'pass' || s === 'fail' || s === 'skipped'
  ).length;
});

const progressPercent = computed(() => {
  if (totalSteps.value === 0) return 0;
  return (completedSteps.value / totalSteps.value) * 100;
});

const canRunAll = computed(() => {
  return props.testPlan && !props.isRunning;
});

const hasFailedSteps = computed(() => {
  return Object.values(props.stepsStatus).some(s => s === 'fail');
});

// Methods
function getStepStatus(stepId) {
  return props.stepsStatus[stepId] || 'pending';
}

function getStepResult(stepId) {
  return props.stepsResults.find(r => r.step_id === stepId);
}

function getStepScreenshot(stepId) {
  return props.screenshots[stepId];
}

function getConnectorClass(index) {
  const prevStep = steps.value[index - 1];
  const prevStatus = getStepStatus(prevStep?.step_id);

  return {
    'pass': prevStatus === 'pass',
    'fail': prevStatus === 'fail',
    'pending': prevStatus === 'pending' || prevStatus === 'skipped'
  };
}

function handleStepClick(step) {
  if (!props.isRunning) {
    emit('run-step', step);
  }
}

function formatTime(ms) {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}m`;
}

// Auto-scroll to current step
watch(() => props.currentStepId, async (newId) => {
  if (newId && pipelineRef.value) {
    await nextTick();
    const stepElements = pipelineRef.value.querySelectorAll('.pipeline-step');
    const index = steps.value.findIndex(s => s.step_id === newId);
    if (index >= 0 && stepElements[index]) {
      stepElements[index].scrollIntoView({
        behavior: 'smooth',
        block: 'nearest',
        inline: 'center'
      });
    }
  }
});
</script>

<style scoped>
.pipeline-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-primary, #0d0d1a);
  color: var(--text-primary, #fff);
}

/* Header */
.pipeline-header {
  padding: 16px;
  border-bottom: 1px solid var(--border-color, #333);
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: center;
  justify-content: space-between;
}

.test-info h3 {
  margin: 0;
  font-size: 1rem;
  color: var(--text-primary, #fff);
}

.test-info p {
  margin: 4px 0 0;
  font-size: 0.8rem;
  color: var(--text-secondary, #999);
}

.pipeline-controls {
  display: flex;
  gap: 8px;
}

.btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: var(--primary, #4ecdc4);
  color: #000;
}

.btn-primary:hover:not(:disabled) {
  background: #3dbdb5;
}

.btn-warning {
  background: #f0ad4e;
  color: #000;
}

.btn-danger {
  background: #d9534f;
  color: #fff;
}

.btn .icon {
  font-size: 0.9rem;
}

/* Progress Bar */
.progress-bar {
  flex: 1;
  min-width: 200px;
  max-width: 400px;
  height: 24px;
  background: var(--bg-tertiary, #1a1a2e);
  border-radius: 12px;
  overflow: hidden;
  position: relative;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--primary, #4ecdc4), #5cb85c);
  transition: width 0.3s ease;
}

.progress-text {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-primary, #fff);
}

/* Pipeline Steps */
.pipeline-steps {
  flex: 1;
  display: flex;
  overflow-x: auto;
  overflow-y: hidden;
  padding: 24px;
  gap: 0;
  align-items: flex-start;
}

.pipeline-step {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

/* Connector */
.connector {
  width: 40px;
  height: 2px;
  background: var(--border-color, #333);
  margin: 0 -1px;
  align-self: center;
  transform: translateY(-50%);
  margin-top: 50px;
}

.connector.pass {
  background: #5cb85c;
}

.connector.fail {
  background: #d9534f;
}

/* Empty State */
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary, #999);
  padding: 48px;
  text-align: center;
}

.empty-icon {
  font-size: 4rem;
  margin-bottom: 16px;
  opacity: 0.5;
}

.empty-state h4 {
  margin: 0 0 8px;
  color: var(--text-primary, #fff);
}

.empty-state p {
  margin: 0;
  font-size: 0.9rem;
}

/* Summary Panel */
.summary-panel {
  padding: 16px;
  border-top: 1px solid var(--border-color, #333);
  background: var(--bg-secondary, #151528);
}

.summary-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.summary-header h4 {
  margin: 0;
  font-size: 0.9rem;
}

.overall-status {
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 0.8rem;
  font-weight: 600;
}

.overall-status.pass {
  background: #5cb85c;
  color: #fff;
}

.overall-status.fail {
  background: #d9534f;
  color: #fff;
}

.summary-stats {
  display: flex;
  gap: 24px;
}

.stat {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.stat-value {
  font-size: 1.5rem;
  font-weight: 700;
}

.stat-value.pass { color: #5cb85c; }
.stat-value.fail { color: #d9534f; }
.stat-value.skip { color: #777; }
.stat-value.time { color: var(--text-primary, #fff); }

.stat-label {
  font-size: 0.7rem;
  color: var(--text-secondary, #999);
  text-transform: uppercase;
}
</style>
