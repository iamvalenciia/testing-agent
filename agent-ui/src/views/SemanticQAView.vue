<template>
  <div class="semantic-qa-view" :class="{ 'dark-mode': uiStore.isDark }">
    <!-- Header -->
    <header class="qa-header">
      <div class="header-left">
        <h1>Semantic QA</h1>
        <span class="connection-status" :class="connectionStatusClass">
          {{ isConnected ? 'Connected' : 'Disconnected' }}
        </span>
      </div>

      <div class="header-right">
        <button class="btn-icon" @click="uiStore.toggleTheme" title="Toggle Theme">
          <svg v-if="uiStore.isDark" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="5"></circle>
            <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"></path>
          </svg>
          <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
          </svg>
        </button>

        <button
          v-if="hasBrowser"
          class="btn-icon btn-danger"
          @click="closeBrowser"
          title="Close Browser"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="15" y1="9" x2="9" y2="15"></line>
            <line x1="9" y1="9" x2="15" y2="15"></line>
          </svg>
        </button>
      </div>
    </header>

    <!-- Main Content -->
    <main class="qa-main">
      <!-- Left Panel: JSON Editor -->
      <section class="editor-panel glass-panel">
        <div class="panel-header">
          <h2>Test Plan</h2>
          <div class="panel-actions">
            <button class="btn-small" @click="loadSamplePlan" title="Load Sample">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
                <line x1="16" y1="13" x2="8" y2="13"></line>
                <line x1="16" y1="17" x2="8" y2="17"></line>
              </svg>
              Sample
            </button>
            <button class="btn-small" @click="formatJson" title="Format JSON">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                <polyline points="4 17 10 11 4 5"></polyline>
                <line x1="12" y1="19" x2="20" y2="19"></line>
              </svg>
              Format
            </button>
          </div>
        </div>

        <textarea
          v-model="jsonInput"
          class="json-editor"
          placeholder='Paste your JSON test plan here...

Example:
{
  "test_case_id": "TC-001",
  "description": "Login test",
  "steps": [
    {
      "step_id": 1,
      "action": "navigate",
      "target": "https://example.com",
      "expected_visual": "Homepage visible"
    }
  ]
}'
          spellcheck="false"
          @input="onJsonInput"
        ></textarea>

        <!-- Validation Status -->
        <div v-if="validationResult" class="validation-banner" :class="validationResult.valid ? 'valid' : 'invalid'">
          <span v-if="validationResult.valid" class="validation-icon">&#10003;</span>
          <span v-else class="validation-icon">&#10007;</span>
          <span v-if="validationResult.valid">
            Valid: {{ validationResult.total_steps }} steps detected
          </span>
          <span v-else>{{ validationResult.error }}</span>
        </div>

        <!-- Execute Button -->
        <button
          class="btn-execute"
          :disabled="!isValidPlan || testPlanStore.isRunning"
          @click="executeTestPlan"
        >
          <svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
            <polygon points="5 3 19 12 5 21 5 3"></polygon>
          </svg>
          {{ testPlanStore.isRunning ? 'Executing...' : 'Execute Test Plan' }}
        </button>
      </section>

      <!-- Center Panel: Live Browser View -->
      <section class="live-panel glass-panel">
        <div class="panel-header">
          <h2>Live View</h2>
          <span v-if="testPlanStore.isRunning" class="live-indicator">
            <span class="pulse-dot"></span>
            LIVE
          </span>
        </div>

        <div class="live-viewport">
          <img
            v-if="currentScreenshot"
            :src="'data:image/png;base64,' + currentScreenshot"
            alt="Browser screenshot"
            class="browser-screenshot"
          />
          <div v-else class="no-screenshot">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="64" height="64">
              <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>
              <line x1="8" y1="21" x2="16" y2="21"></line>
              <line x1="12" y1="17" x2="12" y2="21"></line>
            </svg>
            <p>Browser preview will appear here</p>
          </div>
        </div>
      </section>

      <!-- Right Panel: Pipeline -->
      <section class="pipeline-panel glass-panel">
        <PipelineView
          :test-plan="testPlanStore.testPlan"
          :steps-status="testPlanStore.stepsStatus"
          :steps-results="testPlanStore.stepsResults"
          :current-step-id="testPlanStore.currentStepId"
          :is-running="testPlanStore.isRunning"
          :execution-result="testPlanStore.executionResult"
          :screenshots="testPlanStore.screenshots"
          :is-dark="uiStore.isDark"
          @run-all="executeTestPlan"
          @run-step="executeStep"
          @resume="resumeExecution"
          @stop="stopExecution"
          @view-screenshot="viewScreenshot"
        />
      </section>
    </main>

    <!-- Screenshot Modal -->
    <div v-if="zoomedScreenshot" class="screenshot-modal" @click="zoomedScreenshot = null">
      <div class="screenshot-container" @click.stop>
        <img :src="'data:image/png;base64,' + zoomedScreenshot" alt="Screenshot" />
        <button class="close-btn" @click="zoomedScreenshot = null">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>
    </div>

    <!-- Toast -->
    <div v-if="uiStore.toast" class="toast" :class="uiStore.toast.type">
      {{ uiStore.toast.message }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import PipelineView from '../components/PipelineView.vue'
import { useUiStore } from '../stores/ui'
import { useTestPlanStore } from '../stores/testPlan'

const uiStore = useUiStore()
const testPlanStore = useTestPlanStore()

// Local state
const jsonInput = ref('')
const validationResult = ref(null)
const zoomedScreenshot = ref(null)
let validateTimeout = null

// Computed
const isConnected = computed(() => testPlanStore.isConnected)
const connectionStatusClass = computed(() => isConnected.value ? 'connected' : 'disconnected')
const isValidPlan = computed(() => validationResult.value?.valid === true)
const hasBrowser = computed(() => !!testPlanStore.currentStepId || testPlanStore.isRunning)

const currentScreenshot = computed(() => {
  // Show the latest screenshot from the current step
  if (testPlanStore.currentStepId && testPlanStore.screenshots[testPlanStore.currentStepId]) {
    return testPlanStore.screenshots[testPlanStore.currentStepId]
  }
  // Or show the most recent screenshot from any step
  const stepIds = Object.keys(testPlanStore.screenshots)
  if (stepIds.length > 0) {
    return testPlanStore.screenshots[stepIds[stepIds.length - 1]]
  }
  return null
})

// Methods
function loadSamplePlan() {
  const samplePlan = {
    test_case_id: "TC-001-DEMO",
    description: "Demo test case - Google search",
    tags: ["demo", "search"],
    steps: [
      {
        step_id: 1,
        action: "navigate",
        target: "https://www.google.com",
        expected_visual: "Google homepage with search input visible"
      },
      {
        step_id: 2,
        action: "input",
        target_description: "Search input field",
        value: "Semantic QA Testing",
        expected_visual: "Text visible in search field"
      },
      {
        step_id: 3,
        action: "click",
        target_description: "Google Search button",
        expected_visual: "Search results page displayed"
      },
      {
        step_id: 4,
        action: "verify",
        expected_visual: "Search results visible with relevant links"
      }
    ]
  }
  jsonInput.value = JSON.stringify(samplePlan, null, 2)
  validatePlan()
}

function formatJson() {
  try {
    const parsed = JSON.parse(jsonInput.value)
    jsonInput.value = JSON.stringify(parsed, null, 2)
  } catch (e) {
    uiStore.showToast('Invalid JSON - cannot format', 'error')
  }
}

function onJsonInput() {
  validationResult.value = null
  clearTimeout(validateTimeout)
  validateTimeout = setTimeout(() => {
    if (jsonInput.value.trim()) {
      validatePlan()
    }
  }, 500)
}

async function validatePlan() {
  if (!jsonInput.value.trim()) {
    validationResult.value = { valid: false, error: 'No test plan provided' }
    return
  }

  try {
    const testPlan = JSON.parse(jsonInput.value)

    // Call backend validation
    const response = await fetch('http://localhost:8000/test-plans/validate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ test_plan: testPlan })
    })

    const result = await response.json()
    validationResult.value = result

    if (result.valid) {
      testPlanStore.setTestPlan(testPlan)
    }
  } catch (e) {
    validationResult.value = {
      valid: false,
      error: e.message || 'Invalid JSON format'
    }
  }
}

function executeTestPlan() {
  if (!isValidPlan.value || testPlanStore.isRunning) return

  try {
    const testPlan = JSON.parse(jsonInput.value)
    testPlanStore.setTestPlan(testPlan)
    testPlanStore.executeTestPlan()
  } catch (e) {
    uiStore.showToast('Failed to execute: ' + e.message, 'error')
  }
}

function executeStep(step) {
  testPlanStore.executeStep(step)
}

function resumeExecution() {
  testPlanStore.resumeFromFailure()
}

function stopExecution() {
  testPlanStore.stopExecution()
}

function closeBrowser() {
  testPlanStore.closeBrowser()
}

function viewScreenshot(screenshot) {
  zoomedScreenshot.value = screenshot
}

// Lifecycle
onMounted(() => {
  testPlanStore.connect()
})

onUnmounted(() => {
  testPlanStore.disconnect()
})
</script>

<style scoped>
.semantic-qa-view {
  height: 100vh;
  max-height: 100vh;
  background: var(--bg-primary, #0d0d1a);
  color: var(--text-primary, #fff);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Header */
.qa-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background: var(--bg-secondary, #151528);
  border-bottom: 1px solid var(--border-color, #333);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-left h1 {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 700;
  background: linear-gradient(135deg, var(--primary, #4ecdc4), #667eea);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.connection-status {
  font-size: 0.65rem;
  padding: 3px 8px;
  border-radius: 10px;
  font-weight: 600;
}

.connection-status.connected {
  background: rgba(34, 197, 94, 0.2);
  color: #22c55e;
}

.connection-status.disconnected {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
}

.header-right {
  display: flex;
  gap: 6px;
}

.btn-icon {
  width: 32px;
  height: 32px;
  border: 1px solid var(--border-color, #333);
  background: var(--bg-tertiary, #1a1a2e);
  color: var(--text-primary, #fff);
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.btn-icon:hover {
  background: var(--bg-secondary, #252540);
  border-color: var(--text-secondary, #666);
}

.btn-icon.btn-danger:hover {
  background: rgba(239, 68, 68, 0.2);
  border-color: #ef4444;
  color: #ef4444;
}

.btn-icon svg {
  width: 16px;
  height: 16px;
}

/* Main Content - Flexible grid */
.qa-main {
  flex: 1;
  display: grid;
  grid-template-columns: minmax(200px, 280px) minmax(300px, 1fr) minmax(250px, 320px);
  gap: 10px;
  padding: 10px;
  min-height: 0;
  overflow: hidden;
}

.glass-panel {
  background: rgba(26, 26, 46, 0.8);
  border: 1px solid var(--border-color, #333);
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid var(--border-color, #333);
  background: var(--bg-secondary, #151528);
  flex-shrink: 0;
}

.panel-header h2 {
  margin: 0;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-secondary, #999);
}

.panel-actions {
  display: flex;
  gap: 4px;
}

.btn-small {
  display: flex;
  align-items: center;
  gap: 3px;
  padding: 4px 8px;
  border: 1px solid var(--border-color, #333);
  background: var(--bg-tertiary, #1a1a2e);
  color: var(--text-secondary, #999);
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.65rem;
  transition: all 0.2s ease;
}

.btn-small svg {
  width: 12px;
  height: 12px;
}

.btn-small:hover {
  background: var(--bg-secondary, #252540);
  color: var(--text-primary, #fff);
  border-color: var(--text-secondary, #666);
}

/* Editor Panel */
.editor-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.json-editor {
  flex: 1;
  width: 100%;
  padding: 10px;
  background: transparent;
  border: none;
  color: var(--text-primary, #fff);
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 0.7rem;
  line-height: 1.5;
  resize: none;
  min-height: 0;
}

.json-editor:focus {
  outline: none;
}

.json-editor::placeholder {
  color: var(--text-tertiary, #555);
  font-size: 0.65rem;
}

.validation-banner {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  font-size: 0.7rem;
  font-weight: 500;
  flex-shrink: 0;
}

.validation-banner.valid {
  background: rgba(34, 197, 94, 0.1);
  color: #22c55e;
  border-top: 1px solid rgba(34, 197, 94, 0.3);
}

.validation-banner.invalid {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
  border-top: 1px solid rgba(239, 68, 68, 0.3);
}

.validation-icon {
  font-size: 0.85rem;
}

.btn-execute {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin: 10px;
  padding: 10px 16px;
  background: var(--primary, #4ecdc4);
  color: #000;
  border: none;
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.btn-execute svg {
  width: 14px;
  height: 14px;
}

.btn-execute:hover:not(:disabled) {
  background: #3dbdb5;
  transform: translateY(-1px);
}

.btn-execute:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

/* Live Panel */
.live-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.live-indicator {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 0.6rem;
  font-weight: 700;
  color: #ef4444;
  letter-spacing: 0.5px;
}

.pulse-dot {
  width: 6px;
  height: 6px;
  background: #ef4444;
  border-radius: 50%;
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.8); }
}

.live-viewport {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px;
  background: #000;
  overflow: hidden;
  min-height: 0;
}

.browser-screenshot {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  border-radius: 4px;
}

.no-screenshot {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-tertiary, #555);
  text-align: center;
}

.no-screenshot svg {
  margin-bottom: 8px;
  opacity: 0.5;
  width: 48px;
  height: 48px;
}

.no-screenshot p {
  margin: 0;
  font-size: 0.75rem;
}

/* Pipeline Panel */
.pipeline-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

/* Screenshot Modal */
.screenshot-modal {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 40px;
}

.screenshot-container {
  position: relative;
  max-width: 100%;
  max-height: 100%;
}

.screenshot-container img {
  max-width: 100%;
  max-height: calc(100vh - 80px);
  object-fit: contain;
  border-radius: 8px;
}

.close-btn {
  position: absolute;
  top: -40px;
  right: 0;
  width: 36px;
  height: 36px;
  border: none;
  background: var(--bg-tertiary, #1a1a2e);
  color: var(--text-primary, #fff);
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.close-btn:hover {
  background: #ef4444;
}

.close-btn svg {
  width: 20px;
  height: 20px;
}

/* Toast */
.toast {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  padding: 12px 24px;
  border-radius: 8px;
  font-size: 0.85rem;
  font-weight: 500;
  z-index: 1001;
  animation: slideUp 0.3s ease;
}

.toast.success {
  background: #22c55e;
  color: #fff;
}

.toast.error {
  background: #ef4444;
  color: #fff;
}

.toast.warning {
  background: #f0ad4e;
  color: #000;
}

.toast.info {
  background: var(--primary, #4ecdc4);
  color: #000;
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateX(-50%) translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
}

/* Responsive */
@media (max-width: 1400px) {
  .qa-main {
    grid-template-columns: minmax(180px, 250px) minmax(250px, 1fr) minmax(220px, 280px);
  }
}

@media (max-width: 1100px) {
  .qa-main {
    grid-template-columns: 1fr 1fr;
    grid-template-rows: 1fr 1fr;
  }

  .editor-panel {
    grid-column: 1;
    grid-row: 1 / -1;
  }

  .live-panel {
    grid-column: 2;
    grid-row: 1;
  }

  .pipeline-panel {
    grid-column: 2;
    grid-row: 2;
  }
}

@media (max-width: 768px) {
  .qa-header {
    padding: 8px 12px;
  }

  .header-left h1 {
    font-size: 0.9rem;
  }

  .qa-main {
    grid-template-columns: 1fr;
    grid-template-rows: auto auto auto;
    gap: 8px;
    padding: 8px;
  }

  .editor-panel,
  .live-panel,
  .pipeline-panel {
    grid-column: 1;
    grid-row: auto;
    min-height: 250px;
  }
}
</style>
