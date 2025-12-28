<template>
  <section class="step-log">
    <header class="step-log-header">
      <h2>
        Actions
        <span v-if="steps.length" class="step-count">{{ steps.length }}</span>
      </h2>
      
      <div class="header-actions">
        <!-- Stop Testing Button -->
        <button 
          v-if="isRunning"
          class="action-btn stop"
          @click="$emit('stop-task')"
        >
          Stop Testing
        </button>

        <!-- Save Workflow Button -->
        <button 
          v-if="steps.length > 0 && !isRunning"
          class="action-btn save"
          @click="openSaveDialog"
        >
          Save Workflow
        </button>

        <!-- Download Report Button -->
        <button 
          v-if="steps.length > 0"
          class="action-btn download"
          @click="$emit('download-report')"
          title="Download Report"
        >
          📥
        </button>

        <!-- End Session Button - Closes browser and clears all data -->
        <button 
          v-if="(steps.length > 0 || hasBrowser) && !isRunning"
          class="action-btn end-session"
          @click="$emit('end-session')"
          title="End Session - Close browser and clear all data"
        >
          🛑 End Session
        </button>
      </div>
    </header>

    <div class="step-list" ref="stepListRef">
      <div
        v-for="step in steps"
        :key="step.step_number"
        class="step-item"
      >
        <div class="step-number">{{ step.step_number }}</div>
        <div class="step-content">
          <div class="step-action">{{ formatAction(step.action_type) }}</div>
          <div class="step-details">{{ formatArgs(step) }}</div>
        </div>
        <div class="step-time">{{ formatTime(step.timestamp) }}</div>
      </div>

      <div v-if="steps.length === 0" class="step-item empty">
        <div class="step-content">
           <div class="step-details" style="text-align:center;">
             Waiting for actions...
           </div>
        </div>
      </div>
    </div>

    <!-- Save Workflow Dialog -->
    <Teleport to="body">
      <div v-if="showSaveDialog" class="dialog-overlay" @click.self="closeSaveDialog">
        <div class="dialog-content">
          <!-- Close button -->
          <button class="dialog-close" @click="closeSaveDialog">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M18 6L6 18M6 6l12 12"/>
            </svg>
          </button>

          <!-- Header with gradient icon -->
          <div class="dialog-header">
            <div class="header-icon">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>
                <polyline points="17 21 17 13 7 13 7 21"/>
                <polyline points="7 3 7 8 15 8"/>
              </svg>
            </div>
            <div class="header-text">
              <h3>Save Workflow</h3>
              <p class="dialog-subtitle">Create a reusable workflow from these {{ steps.length }} steps</p>
            </div>
          </div>
          
          <div class="form-group">
            <label>
              <span class="label-icon">📝</span>
              Workflow Name
            </label>
            <input 
              v-model="workflowName" 
              type="text" 
              placeholder="e.g., Login to Portal, Download Hammer..."
              class="form-input"
              autofocus
            />
          </div>
          
          <div class="form-group">
            <label>
              <span class="label-icon">📁</span>
              Category
            </label>
            <div class="category-grid">
              <button 
                v-for="cat in categories" 
                :key="cat.value"
                class="category-btn"
                :class="{ active: selectedCategory === cat.value }"
                @click="selectedCategory = cat.value"
              >
                <div class="category-icon-wrapper" :class="cat.value">
                  <span class="category-icon">{{ cat.icon }}</span>
                </div>
                <div class="category-text">
                  <span class="category-label">{{ cat.label }}</span>
                  <span class="category-desc">{{ cat.desc }}</span>
                </div>
                <div v-if="selectedCategory === cat.value" class="check-mark">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                    <polyline points="20 6 9 17 4 12"/>
                  </svg>
                </div>
              </button>
            </div>
          </div>
          
          <div class="form-group">
            <label>
              <span class="label-icon">💬</span>
              Description 
              <span class="label-optional">(optional)</span>
            </label>
            <textarea 
              v-model="workflowDescription" 
              placeholder="Describe what this workflow does and when to use it..."
              class="form-textarea"
              rows="3"
            ></textarea>
          </div>
          
          <div class="dialog-actions">
            <button class="btn-secondary" @click="closeSaveDialog">
              Cancel
            </button>
            <button 
              class="btn-primary" 
              @click="saveWorkflow"
              :disabled="!workflowName || !selectedCategory"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>
                <polyline points="17 21 17 13 7 13 7 21"/>
                <polyline points="7 3 7 8 15 8"/>
              </svg>
              Save Workflow
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </section>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'

const props = defineProps({
  steps: {
    type: Array,
    default: () => []
  },
  isRunning: {
    type: Boolean,
    default: false
  },
  taskId: {
    type: String,
    default: null
  },
  hasBrowser: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['save-workflow', 'stop-task', 'download-report', 'close-browser', 'end-session'])

const stepListRef = ref(null)

// Save dialog state
const showSaveDialog = ref(false)
const workflowName = ref('')
const workflowDescription = ref('')
const selectedCategory = ref('')

const categories = [
  { 
    value: 'steps', 
    label: 'Navigation Steps', 
    icon: '🔄',
    desc: 'Reusable UI navigation'
  },
  { 
    value: 'hammer-indexer', 
    label: 'Hammer Indexer', 
    icon: '🔨',
    desc: 'Download & index hammer data'
  },
  { 
    value: 'jira-indexer', 
    label: 'Jira Indexer', 
    icon: '📋',
    desc: 'Fetch & index Jira tickets'
  },
  { 
    value: 'zendesk-indexer', 
    label: 'Zendesk Indexer', 
    icon: '📚',
    desc: 'Scrape & index Zendesk docs'
  }
]

function openSaveDialog() {
  showSaveDialog.value = true
  workflowName.value = ''
  workflowDescription.value = ''
  selectedCategory.value = ''
}

function closeSaveDialog() {
  showSaveDialog.value = false
}

function saveWorkflow() {
  if (!workflowName.value || !selectedCategory.value) return
  
  emit('save-workflow', {
    name: workflowName.value,
    description: workflowDescription.value,
    category: selectedCategory.value,
    taskId: props.taskId
  })
  
  closeSaveDialog()
}

function formatAction(actionType) {
  const actionMap = {
    'click_at': 'Click',
    'type_text_at': 'Type',
    'navigate': 'Navigate',
    'scroll_document': 'Scroll',
    'scroll_at': 'Scroll',
    'key_combination': 'Key',
    'wait_5_seconds': 'Wait',
    'go_back': 'Back',
    'go_forward': 'Forward',
    'hover_at': 'Hover',
    'open_web_browser': 'Open Browser',
    'search': 'Search',
    'drag_and_drop': 'Drag'
  }
  return actionMap[actionType] || actionType
}

function formatArgs(step) {
  const args = step.args
  if (step.action_type === 'click_at') {
    return `(${args.x}, ${args.y})`
  }
  if (step.action_type === 'type_text_at') {
    const text = args.text?.length > 25 ? args.text.slice(0, 25) + '...' : args.text
    return `"${text}"`
  }
  if (step.action_type === 'navigate') {
    const url = args.url?.length > 30 ? args.url.slice(0, 30) + '...' : args.url
    return url
  }
  if (step.action_type === 'scroll_document' || step.action_type === 'scroll_at') {
    return args.direction
  }
  if (step.action_type === 'key_combination') {
    return args.keys
  }
  return ''
}

function formatTime(timestamp) {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  return date.toLocaleTimeString('en-US', { 
    hour: '2-digit', 
    minute: '2-digit',
    second: '2-digit'
  })
}

// Auto-scroll to bottom
watch(() => props.steps.length, async () => {
  await nextTick()
  if (stepListRef.value) {
    stepListRef.value.scrollTop = stepListRef.value.scrollHeight
  }
})
</script>

<style scoped>

/* Header Actions */
.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* Base Action Button */
.action-btn {
  background: white;
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  padding: 6px 12px;
  border-radius: var(--radius-sm);
  font-size: 0.75rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: var(--shadow-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  height: 28px;
}

.action-btn:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}

/* Save Btn */
.action-btn.save {
  background: var(--bg-elevated);
  border-color: var(--accent-primary);
  color: var(--accent-primary);
}

.action-btn.save:hover {
  background: var(--accent-primary);
  color: white;
  box-shadow: var(--shadow-color);
}

/* Stop Btn */
.action-btn.stop {
  background: rgba(239, 68, 68, 0.1);
  color: var(--error);
  border-color: rgba(239, 68, 68, 0.3);
}

.action-btn.stop:hover {
  background: var(--error);
  color: white;
  box-shadow: 0 0 10px rgba(239, 68, 68, 0.4);
}

/* Download Btn */
.action-btn.download {
  background: var(--bg-elevated);
  font-size: 1rem;
  padding: 0 8px;
}

.action-btn.download:hover {
  background: var(--bg-tertiary);
  color: white;
}

/* Close Browser Btn */
.action-btn.close {
  background: var(--bg-elevated);
  color: var(--text-muted);
  font-size: 0.9rem;
  padding: 0 8px;
}

.action-btn.close:hover {
  background: rgba(239, 68, 68, 0.2);
  color: var(--error);
  border-color: rgba(239, 68, 68, 0.3);
}

/* End Session Btn */
.action-btn.end-session {
  background: rgba(220, 38, 38, 0.1);
  color: #dc2626;
  border-color: rgba(220, 38, 38, 0.3);
  font-weight: 600;
}

.action-btn.end-session:hover {
  background: #dc2626;
  color: white;
  border-color: #dc2626;
  box-shadow: 0 0 12px rgba(220, 38, 38, 0.4);
}

/* Dialog Overlay */
.dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(15, 23, 42, 0.6);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  animation: fadeIn 0.2s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.dialog-content {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, rgba(248, 250, 252, 0.98) 100%);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.8);
  border-radius: 20px;
  padding: 28px 32px 32px;
  width: 90%;
  max-width: 520px;
  box-shadow: 
    0 25px 50px -12px rgba(0, 0, 0, 0.25),
    0 0 0 1px rgba(0, 0, 0, 0.05),
    inset 0 1px 0 rgba(255, 255, 255, 0.8);
  animation: dialogSlideUp 0.35s cubic-bezier(0.16, 1, 0.3, 1);
  position: relative;
  overflow: hidden;
}

.dialog-content::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background: linear-gradient(90deg, #6366f1, #8b5cf6, #a855f7);
}

@keyframes dialogSlideUp {
  from { 
    opacity: 0; 
    transform: translateY(24px) scale(0.96); 
  }
  to { 
    opacity: 1; 
    transform: translateY(0) scale(1); 
  }
}

/* Close Button */
.dialog-close {
  position: absolute;
  top: 16px;
  right: 16px;
  width: 36px;
  height: 36px;
  border: none;
  background: rgba(100, 116, 139, 0.08);
  border-radius: 10px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: all 0.2s;
}

.dialog-close:hover {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
  transform: rotate(90deg);
}

/* Dialog Header */
.dialog-header {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 28px;
}

.header-icon {
  width: 56px;
  height: 56px;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  flex-shrink: 0;
  box-shadow: 0 8px 16px -4px rgba(99, 102, 241, 0.4);
}

.header-text {
  flex: 1;
  padding-top: 4px;
}

.dialog-content h3 {
  margin: 0 0 4px 0;
  font-size: 1.4rem;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.02em;
}

.dialog-subtitle {
  margin: 0;
  color: var(--text-secondary);
  font-size: 0.9rem;
  line-height: 1.4;
}

/* Form Elements */
.form-group {
  margin-bottom: 22px;
}

.form-group label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 10px;
}

.label-icon {
  font-size: 0.95rem;
}

.label-optional {
  font-weight: 400;
  text-transform: none;
  color: var(--text-muted);
  font-size: 0.75rem;
}

.form-input,
.form-textarea {
  width: 100%;
  padding: 14px 16px;
  background: white;
  border: 2px solid var(--border-color);
  border-radius: 12px;
  font-size: 0.95rem;
  font-family: inherit;
  color: var(--text-primary);
  transition: all 0.2s;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.form-input::placeholder,
.form-textarea::placeholder {
  color: var(--text-muted);
}

.form-input:focus,
.form-textarea:focus {
  outline: none;
  border-color: var(--accent-primary);
  box-shadow: 
    0 0 0 4px var(--accent-soft),
    0 1px 3px rgba(0, 0, 0, 0.04);
  background: white;
}

.form-textarea {
  resize: vertical;
  min-height: 90px;
  line-height: 1.5;
}

/* Category Grid */
.category-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.category-btn {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  background: white;
  border: 2px solid var(--border-color);
  border-radius: 14px;
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  text-align: left;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.02);
}

.category-btn:hover {
  border-color: rgba(99, 102, 241, 0.3);
  transform: translateY(-2px);
  box-shadow: 0 8px 16px -4px rgba(0, 0, 0, 0.08);
}

.category-btn.active {
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.04) 0%, rgba(139, 92, 246, 0.04) 100%);
  border-color: var(--accent-primary);
  box-shadow: 
    0 0 0 4px var(--accent-soft),
    0 4px 12px -4px rgba(99, 102, 241, 0.2);
}

.category-icon-wrapper {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: transform 0.2s;
}

.category-btn:hover .category-icon-wrapper {
  transform: scale(1.08);
}

/* Category colors */
.category-icon-wrapper.steps {
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  box-shadow: 0 4px 12px -2px rgba(59, 130, 246, 0.35);
}

.category-icon-wrapper.hammer-indexer {
  background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%);
  box-shadow: 0 4px 12px -2px rgba(139, 92, 246, 0.35);
}

.category-icon-wrapper.jira-indexer {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  box-shadow: 0 4px 12px -2px rgba(16, 185, 129, 0.35);
}

.category-icon-wrapper.zendesk-indexer {
  background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
  box-shadow: 0 4px 12px -2px rgba(245, 158, 11, 0.35);
}

.category-icon {
  font-size: 1.3rem;
  filter: brightness(0) invert(1);
}

.category-text {
  flex: 1;
  min-width: 0;
}

.category-label {
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--text-primary);
  display: block;
  margin-bottom: 2px;
}

.category-desc {
  font-size: 0.72rem;
  color: var(--text-muted);
  line-height: 1.3;
  display: block;
}

.check-mark {
  position: absolute;
  top: -6px;
  right: -6px;
  width: 24px;
  height: 24px;
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  box-shadow: 0 2px 8px rgba(16, 185, 129, 0.4);
  animation: popIn 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes popIn {
  from { 
    transform: scale(0); 
    opacity: 0; 
  }
  to { 
    transform: scale(1); 
    opacity: 1; 
  }
}

/* Dialog Actions */
.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 28px;
  padding-top: 24px;
  border-top: 1px solid var(--border-color);
}

.btn-secondary,
.btn-primary {
  padding: 12px 24px;
  border-radius: 12px;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.btn-secondary {
  background: transparent;
  border: 2px solid var(--border-dark);
  color: var(--text-secondary);
}

.btn-secondary:hover {
  background: var(--bg-primary);
  color: var(--text-primary);
  border-color: var(--text-muted);
}

.btn-primary {
  background: linear-gradient(135deg, #6366f1 0%, #7c3aed 100%);
  border: none;
  color: white;
  box-shadow: 
    0 4px 14px -2px rgba(99, 102, 241, 0.45),
    inset 0 1px 0 rgba(255, 255, 255, 0.15);
  padding: 12px 28px;
}

.btn-primary:hover:not(:disabled) {
  background: linear-gradient(135deg, #4f46e5 0%, #6d28d9 100%);
  transform: translateY(-2px);
  box-shadow: 
    0 8px 20px -4px rgba(99, 102, 241, 0.55),
    inset 0 1px 0 rgba(255, 255, 255, 0.15);
}

.btn-primary:active:not(:disabled) {
  transform: translateY(0);
}

.btn-primary:disabled {
  background: linear-gradient(135deg, #94a3b8 0%, #64748b 100%);
  cursor: not-allowed;
  box-shadow: none;
  opacity: 0.6;
}

/* Empty state */
.step-item.empty {
  opacity: 0.6;
  background: transparent;
  border: 2px dashed var(--border-color);
  box-shadow: none;
  justify-content: center;
  padding: 30px;
  border-radius: var(--radius-md);
}
</style>
