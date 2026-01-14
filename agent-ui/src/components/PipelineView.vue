<template>
  <div class="pipeline-container" :class="{ 'dark-mode': isDark }">
    <!-- Pipeline Header -->
    <div class="pipeline-header">
      <div class="test-info">
        <h3 v-if="testPlan">{{ testPlan.test_case_id }}</h3>
        <p v-if="testPlan">{{ testPlan.description }}</p>
        <div v-if="testPlan?.tags" class="tags">
          <span v-for="tag in testPlan.tags" :key="tag" class="tag">{{ tag }}</span>
        </div>
      </div>

      <div class="pipeline-controls">
        <button
          v-if="canRunAll"
          class="btn btn-primary"
          @click="$emit('run-all')"
          :disabled="isRunning"
        >
          <svg viewBox="0 0 24 24" fill="currentColor" width="16" height="16">
            <polygon points="5 3 19 12 5 21 5 3"></polygon>
          </svg>
          Run All Steps
        </button>

        <button
          v-if="hasFailedSteps && !isRunning"
          class="btn btn-warning"
          @click="$emit('resume')"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
            <polyline points="23 4 23 10 17 10"></polyline>
            <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
          </svg>
          Resume from Failure
        </button>

        <button
          v-if="isRunning"
          class="btn btn-danger"
          @click="$emit('stop')"
        >
          <svg viewBox="0 0 24 24" fill="currentColor" width="16" height="16">
            <rect x="6" y="6" width="12" height="12"></rect>
          </svg>
          Stop Execution
        </button>
      </div>
    </div>

    <!-- Progress Overview -->
    <div v-if="testPlan" class="progress-overview">
      <div class="progress-bar-container">
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
        </div>
        <span class="progress-label">{{ completedSteps }} / {{ totalSteps }} steps</span>
      </div>

      <div class="progress-stats">
        <div class="stat passed">
          <span class="stat-icon">&#10003;</span>
          <span class="stat-value">{{ passedStepsCount }}</span>
          <span class="stat-label">Passed</span>
        </div>
        <div class="stat failed">
          <span class="stat-icon">&#10007;</span>
          <span class="stat-value">{{ failedStepsCount }}</span>
          <span class="stat-label">Failed</span>
        </div>
        <div class="stat pending">
          <span class="stat-icon">&#9675;</span>
          <span class="stat-value">{{ pendingStepsCount }}</span>
          <span class="stat-label">Pending</span>
        </div>
      </div>
    </div>

    <!-- Vertical Pipeline Steps -->
    <div class="pipeline-steps" ref="pipelineRef">
      <div
        v-for="(step, index) in steps"
        :key="step.step_id"
        class="pipeline-step"
      >
        <!-- Vertical Connector Line (before step) -->
        <div v-if="index > 0" class="connector-vertical" :class="getConnectorClass(index)">
          <div class="connector-line"></div>
        </div>

        <!-- Step Card -->
        <StepCard
          :step="step"
          :result="getStepResult(step.step_id)"
          :status="getStepStatus(step.step_id)"
          :is-active="currentStepId === step.step_id"
          :clickable="!isRunning"
          :screenshot="getStepScreenshot(step.step_id)"
          @click="handleStepClick"
          @run-step="$emit('run-step', $event)"
          @view-screenshot="$emit('view-screenshot', $event)"
        />
      </div>
    </div>

    <!-- Empty State -->
    <div v-if="!testPlan" class="empty-state">
      <div class="empty-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="80" height="80">
          <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path>
          <path d="M9 12h6M9 16h6"></path>
        </svg>
      </div>
      <h4>No Test Plan Loaded</h4>
      <p>Paste a JSON test plan in the editor to begin execution</p>
    </div>

    <!-- Summary Panel (when completed) -->
    <div v-if="executionResult" class="summary-panel" :class="executionResult.overall_status">
      <div class="summary-header">
        <div class="summary-title">
          <h4>Execution Complete</h4>
          <span class="overall-status-badge" :class="executionResult.overall_status">
            {{ executionResult.overall_status === 'pass' ? 'PASSED' : 'FAILED' }}
          </span>
        </div>
        <span class="execution-time">
          Duration: {{ formatTime(executionResult.total_execution_time_ms) }}
        </span>
      </div>

      <div class="summary-stats">
        <div class="summary-stat">
          <span class="summary-value pass">{{ executionResult.passed_steps }}</span>
          <span class="summary-label">Passed</span>
        </div>
        <div class="summary-stat">
          <span class="summary-value fail">{{ executionResult.failed_steps }}</span>
          <span class="summary-label">Failed</span>
        </div>
        <div class="summary-stat">
          <span class="summary-value skip">{{ executionResult.skipped_steps }}</span>
          <span class="summary-label">Skipped</span>
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

const passedStepsCount = computed(() =>
  Object.values(props.stepsStatus).filter(s => s === 'pass').length
);

const failedStepsCount = computed(() =>
  Object.values(props.stepsStatus).filter(s => s === 'fail').length
);

const pendingStepsCount = computed(() =>
  Object.values(props.stepsStatus).filter(s => s === 'pending' || !s).length
);

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
    'running': prevStatus === 'running',
    'pending': prevStatus === 'pending' || prevStatus === 'skipped'
  };
}

function handleStepClick(step) {
  if (!props.isRunning) {
    emit('run-step', step);
  }
}

function formatTime(ms) {
  if (!ms) return '0s';
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
        block: 'center'
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
  min-height: 0;
}

/* Header */
.pipeline-header {
  padding: 10px 12px;
  border-bottom: 1px solid var(--border-color, #333);
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
  flex-wrap: wrap;
  flex-shrink: 0;
}

.test-info h3 {
  margin: 0;
  font-size: 0.85rem;
  color: var(--text-primary, #fff);
  font-weight: 600;
}

.test-info p {
  margin: 3px 0 0;
  font-size: 0.7rem;
  color: var(--text-secondary, #999);
}

.tags {
  display: flex;
  gap: 4px;
  margin-top: 4px;
}

.tag {
  font-size: 0.6rem;
  padding: 1px 6px;
  background: var(--bg-tertiary, #1a1a2e);
  border: 1px solid var(--border-color, #333);
  border-radius: 8px;
  color: var(--text-secondary, #999);
}

.pipeline-controls {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
  flex-wrap: wrap;
}

.btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  border: none;
  border-radius: 5px;
  font-size: 0.65rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn svg {
  width: 12px;
  height: 12px;
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

.btn-warning:hover:not(:disabled) {
  background: #ec971f;
}

.btn-danger {
  background: #ef4444;
  color: #fff;
}

.btn-danger:hover:not(:disabled) {
  background: #dc2626;
}

/* Progress Overview */
.progress-overview {
  padding: 8px 12px;
  background: var(--bg-secondary, #151528);
  border-bottom: 1px solid var(--border-color, #333);
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  flex-shrink: 0;
}

.progress-bar-container {
  flex: 1;
  min-width: 100px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.progress-bar {
  flex: 1;
  height: 4px;
  background: var(--bg-tertiary, #1a1a2e);
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--primary, #4ecdc4), #22c55e);
  border-radius: 2px;
  transition: width 0.3s ease;
}

.progress-label {
  font-size: 0.65rem;
  color: var(--text-secondary, #999);
  white-space: nowrap;
}

.progress-stats {
  display: flex;
  gap: 10px;
}

.stat {
  display: flex;
  align-items: center;
  gap: 3px;
  font-size: 0.65rem;
}

.stat-icon {
  font-size: 0.75rem;
}

.stat.passed .stat-icon { color: #22c55e; }
.stat.failed .stat-icon { color: #ef4444; }
.stat.pending .stat-icon { color: #666; }

.stat-value {
  font-weight: 700;
  font-size: 0.75rem;
}

.stat.passed .stat-value { color: #22c55e; }
.stat.failed .stat-value { color: #ef4444; }
.stat.pending .stat-value { color: var(--text-secondary, #999); }

.stat-label {
  color: var(--text-secondary, #999);
  display: none;
}

/* Pipeline Steps - Vertical Layout */
.pipeline-steps {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 0;
  min-height: 0;
}

.pipeline-step {
  display: flex;
  flex-direction: column;
  align-items: stretch;
}

/* Vertical Connector */
.connector-vertical {
  display: flex;
  justify-content: center;
  padding: 0 0 0 24px;
  height: 12px;
}

.connector-line {
  width: 2px;
  height: 100%;
  background: var(--border-color, #444);
  transition: background 0.3s ease;
}

.connector-vertical.pass .connector-line {
  background: #22c55e;
}

.connector-vertical.fail .connector-line {
  background: #ef4444;
}

.connector-vertical.running .connector-line {
  background: linear-gradient(180deg, #f0ad4e 0%, #f0ad4e 50%, transparent 50%, transparent 100%);
  background-size: 2px 6px;
  animation: dashedLine 0.5s linear infinite;
}

@keyframes dashedLine {
  to {
    background-position: 0 6px;
  }
}

/* Empty State */
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary, #999);
  padding: 24px;
  text-align: center;
}

.empty-icon {
  margin-bottom: 12px;
  opacity: 0.4;
  color: var(--text-secondary, #666);
}

.empty-icon svg {
  width: 48px;
  height: 48px;
}

.empty-state h4 {
  margin: 0 0 4px;
  color: var(--text-primary, #fff);
  font-size: 0.85rem;
}

.empty-state p {
  margin: 0;
  font-size: 0.7rem;
  max-width: 200px;
}

/* Summary Panel */
.summary-panel {
  padding: 10px 12px;
  border-top: 1px solid var(--border-color, #333);
  background: var(--bg-secondary, #151528);
  flex-shrink: 0;
}

.summary-panel.pass {
  border-top: 2px solid #22c55e;
}

.summary-panel.fail {
  border-top: 2px solid #ef4444;
}

.summary-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.summary-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.summary-title h4 {
  margin: 0;
  font-size: 0.75rem;
}

.overall-status-badge {
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 0.6rem;
  font-weight: 700;
  letter-spacing: 0.3px;
}

.overall-status-badge.pass {
  background: #22c55e;
  color: #fff;
}

.overall-status-badge.fail {
  background: #ef4444;
  color: #fff;
}

.execution-time {
  font-size: 0.65rem;
  color: var(--text-secondary, #999);
}

.summary-stats {
  display: flex;
  gap: 16px;
}

.summary-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.summary-value {
  font-size: 1.25rem;
  font-weight: 700;
}

.summary-value.pass { color: #22c55e; }
.summary-value.fail { color: #ef4444; }
.summary-value.skip { color: #777; }

.summary-label {
  font-size: 0.6rem;
  color: var(--text-secondary, #999);
  text-transform: uppercase;
  letter-spacing: 0.3px;
}
</style>
