<template>
  <div class="test-plan-panel" :class="{ 'dark-mode': isDark }">
    <!-- Tab Navigation -->
    <div class="panel-tabs">
      <button
        class="tab"
        :class="{ active: activeTab === 'editor' }"
        @click="activeTab = 'editor'"
      >
        Editor
      </button>
      <button
        class="tab"
        :class="{ active: activeTab === 'execution' }"
        @click="activeTab = 'execution'"
      >
        Execution
      </button>
    </div>

    <!-- Editor Tab -->
    <div v-show="activeTab === 'editor'" class="tab-content editor-tab">
      <!-- JSON Editor -->
      <div class="editor-header">
        <h4>Test Plan JSON</h4>
        <div class="editor-actions">
          <button class="btn-small" @click="loadSample" title="Load Sample">
            &#128203;
          </button>
          <button class="btn-small" @click="formatJson" title="Format JSON">
            &#10003;
          </button>
          <button class="btn-small" @click="validatePlan" title="Validate">
            &#9745;
          </button>
        </div>
      </div>

      <textarea
        v-model="jsonInput"
        class="json-editor"
        placeholder='Paste your test plan JSON here or click the clipboard icon to load a sample...'
        spellcheck="false"
      ></textarea>

      <!-- Validation Status -->
      <div v-if="validationResult" class="validation-status" :class="validationResult.valid ? 'valid' : 'invalid'">
        <span v-if="validationResult.valid">
          &#9989; Valid: {{ validationResult.total_steps }} steps
        </span>
        <span v-else>
          &#10060; {{ validationResult.error }}
        </span>
      </div>

      <!-- Quick Actions -->
      <div class="quick-actions">
        <button
          class="btn btn-primary"
          :disabled="!isValidPlan || isRunning"
          @click="runTestPlan"
        >
          &#9654; Execute Test Plan
        </button>
      </div>
    </div>

    <!-- Execution Tab -->
    <div v-show="activeTab === 'execution'" class="tab-content execution-tab">
      <!-- Execution Options -->
      <div class="execution-options">
        <label class="option">
          <input type="checkbox" v-model="options.stopOnFailure" />
          Stop on failure
        </label>
        <label class="option">
          <span>Max retries:</span>
          <input type="number" v-model.number="options.maxRetries" min="0" max="10" />
        </label>
      </div>

      <!-- Execution Log -->
      <div class="execution-log">
        <div
          v-for="log in executionLogs"
          :key="log.id"
          class="log-entry"
          :class="log.type"
        >
          <span class="log-time">{{ log.time }}</span>
          <span class="log-message">{{ log.message }}</span>
        </div>
        <div v-if="executionLogs.length === 0" class="log-empty">
          Execution logs will appear here...
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue';

const props = defineProps({
  isDark: {
    type: Boolean,
    default: true
  },
  isRunning: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['execute', 'validate']);

// State
const activeTab = ref('editor');
const jsonInput = ref('');
const validationResult = ref(null);
const executionLogs = ref([]);
const options = ref({
  stopOnFailure: true,
  maxRetries: 3
});

// Computed
const isValidPlan = computed(() => validationResult.value?.valid === true);

// Methods
function loadSample() {
  const samplePlan = {
    test_case_id: "TC-001-LOGIN",
    description: "Verify login flow and dashboard access",
    tags: ["smoke", "login", "critical"],
    steps: [
      {
        step_id: 1,
        action: "navigate",
        target: "https://app.example.com/login",
        expected_visual: "Login form visible with email and password fields"
      },
      {
        step_id: 2,
        action: "input",
        target_description: "Email input field",
        value: "user@test.com",
        expected_visual: "Email text visible inside the input field"
      },
      {
        step_id: 3,
        action: "input",
        target_description: "Password input field",
        value: "SecurePass123",
        expected_visual: "Password field shows masked characters"
      },
      {
        step_id: 4,
        action: "click",
        target_description: "Blue 'Sign In' button",
        expected_visual: "Main dashboard visible with user greeting"
      }
    ]
  };

  jsonInput.value = JSON.stringify(samplePlan, null, 2);
  validationResult.value = null;
}

function formatJson() {
  try {
    const parsed = JSON.parse(jsonInput.value);
    jsonInput.value = JSON.stringify(parsed, null, 2);
  } catch (e) {
    // Invalid JSON, can't format
  }
}

async function validatePlan() {
  if (!jsonInput.value.trim()) {
    validationResult.value = { valid: false, error: 'No test plan provided' };
    return;
  }

  try {
    const testPlan = JSON.parse(jsonInput.value);

    // Call backend validation endpoint
    const response = await fetch('http://localhost:8000/test-plans/validate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ test_plan: testPlan })
    });

    const result = await response.json();
    validationResult.value = result;
    emit('validate', result);

  } catch (e) {
    validationResult.value = {
      valid: false,
      error: e.message || 'Invalid JSON format'
    };
  }
}

function runTestPlan() {
  if (!isValidPlan.value) return;

  try {
    const testPlan = JSON.parse(jsonInput.value);
    addLog('info', `Starting execution: ${testPlan.test_case_id}`);

    emit('execute', {
      testPlan,
      options: {
        stopOnFailure: options.value.stopOnFailure,
        maxRetries: options.value.maxRetries
      }
    });

    activeTab.value = 'execution';
  } catch (e) {
    addLog('error', `Failed to start: ${e.message}`);
  }
}

function addLog(type, message) {
  executionLogs.value.push({
    id: Date.now(),
    type,
    time: new Date().toLocaleTimeString(),
    message
  });
}

// Watch for external log updates
defineExpose({
  addLog,
  clearLogs: () => { executionLogs.value = []; }
});

// Auto-validate on input change (debounced)
let validateTimeout = null;
watch(jsonInput, () => {
  validationResult.value = null;
  clearTimeout(validateTimeout);
  validateTimeout = setTimeout(() => {
    if (jsonInput.value.trim()) {
      validatePlan();
    }
  }, 500);
});
</script>

<style scoped>
.test-plan-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-primary, #0d0d1a);
  color: var(--text-primary, #fff);
}

/* Tabs */
.panel-tabs {
  display: flex;
  border-bottom: 1px solid var(--border-color, #333);
}

.tab {
  flex: 1;
  padding: 12px;
  background: transparent;
  border: none;
  color: var(--text-secondary, #999);
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.tab.active {
  color: var(--text-primary, #fff);
  border-bottom: 2px solid var(--primary, #4ecdc4);
}

.tab:hover:not(.active) {
  color: var(--text-primary, #fff);
  background: var(--bg-tertiary, #1a1a2e);
}

/* Tab Content */
.tab-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Editor Tab */
.editor-tab {
  padding: 12px;
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.editor-header h4 {
  margin: 0;
  font-size: 0.9rem;
  color: var(--text-secondary, #999);
}

.editor-actions {
  display: flex;
  gap: 4px;
}

.btn-small {
  width: 28px;
  height: 28px;
  border: 1px solid var(--border-color, #333);
  background: var(--bg-tertiary, #1a1a2e);
  color: var(--text-primary, #fff);
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.9rem;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.btn-small:hover {
  background: var(--bg-secondary, #252540);
  border-color: var(--text-secondary, #666);
}

.json-editor {
  flex: 1;
  width: 100%;
  min-height: 200px;
  padding: 12px;
  background: var(--bg-tertiary, #1a1a2e);
  border: 1px solid var(--border-color, #333);
  border-radius: 6px;
  color: var(--text-primary, #fff);
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 0.8rem;
  line-height: 1.5;
  resize: vertical;
}

.json-editor:focus {
  outline: none;
  border-color: var(--primary, #4ecdc4);
}

/* Validation Status */
.validation-status {
  margin-top: 8px;
  padding: 8px 12px;
  border-radius: 4px;
  font-size: 0.8rem;
}

.validation-status.valid {
  background: rgba(92, 184, 92, 0.2);
  color: #5cb85c;
}

.validation-status.invalid {
  background: rgba(217, 83, 79, 0.2);
  color: #d9534f;
}

/* Quick Actions */
.quick-actions {
  margin-top: 12px;
}

.btn {
  padding: 10px 20px;
  border: none;
  border-radius: 6px;
  font-size: 0.9rem;
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

/* Execution Tab */
.execution-tab {
  padding: 12px;
}

.execution-options {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border-color, #333);
}

.option {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.85rem;
  color: var(--text-secondary, #999);
}

.option input[type="checkbox"] {
  width: 16px;
  height: 16px;
}

.option input[type="number"] {
  width: 60px;
  padding: 4px 8px;
  background: var(--bg-tertiary, #1a1a2e);
  border: 1px solid var(--border-color, #333);
  border-radius: 4px;
  color: var(--text-primary, #fff);
  font-size: 0.85rem;
}

/* Execution Log */
.execution-log {
  flex: 1;
  overflow-y: auto;
  background: var(--bg-tertiary, #1a1a2e);
  border: 1px solid var(--border-color, #333);
  border-radius: 6px;
  padding: 8px;
}

.log-entry {
  display: flex;
  gap: 8px;
  padding: 6px 8px;
  font-size: 0.8rem;
  font-family: 'JetBrains Mono', monospace;
  border-bottom: 1px solid var(--border-color, #222);
}

.log-entry:last-child {
  border-bottom: none;
}

.log-entry.info { color: var(--text-primary, #fff); }
.log-entry.success { color: #5cb85c; }
.log-entry.warning { color: #f0ad4e; }
.log-entry.error { color: #d9534f; }

.log-time {
  color: var(--text-tertiary, #666);
  flex-shrink: 0;
}

.log-message {
  flex: 1;
}

.log-empty {
  text-align: center;
  color: var(--text-tertiary, #666);
  padding: 24px;
  font-style: italic;
}
</style>
