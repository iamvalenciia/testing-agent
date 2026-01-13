<template>
  <Background3D :is-dark="uiStore.isDark" />

  <div class="hud-container" :class="{ 'light-mode': !uiStore.isDark }">
    <!-- Header Component -->
    <TheHeader 
      :connection-status-class="sessionStore.connectionStatusClass"
      :is-production-mode="sessionStore.isProductionMode"
      :is-dark="uiStore.isDark"
      :is-running="sessionStore.isRunning"
      :has-browser="sessionStore.hasBrowser"
      :has-steps="sessionStore.steps.length > 0"
      :is-saving="isSavingStaticData"
      :user="authStore.user"
      :hammer-metadata="hammerMetadata"
      @toggle-mode="sessionStore.toggleMode"
      @toggle-theme="uiStore.toggleTheme"
      @close-browser="sessionStore.closeBrowser"
      @open-workflow="openWorkflowModal"
      @open-report="openReportModal"
      @open-success="openSuccessModal"
      @open-static="openStaticDataModal"
      @open-hammer="openHammerModal"
      @end-session="sessionStore.endSession"
      @logout="handleLogout"
    />

    <!-- Main Grid -->
    <main class="main-grid">
      <!-- Left: Mission Control (Chat) -->
      <section class="glass-panel control-panel">
        <h2>MISSION CONTROL</h2>
        <ChatPanel 
          :messages="sessionStore.messages" 
          :status="sessionStore.taskStatus"
          :is-dark="uiStore.isDark"
          @send-message="sessionStore.sendMessage" 
          @stop="sessionStore.stopTask"
        />
      </section>

      <!-- Center: Viewport (Live View) + Steps -->
      <section class="viewport-panel">
        <div style="flex: 1; min-height: 0; position: relative;">
          <LiveView 
            :screenshot="sessionStore.currentScreenshot" 
            :status="sessionStore.taskStatus"
            :is-dark="uiStore.isDark"
          />
        </div>
        <div style="height: 160px; min-height: 160px;">
          <StepLog :steps="sessionStore.steps" :is-dark="uiStore.isDark" @view-image="handleViewImage" />
        </div>
      </section>
    </main>

    <!-- ==================== MODALS ==================== -->

    <!-- Save Workflow Modal -->
    <div 
      v-if="showWorkflowModal" 
      class="modal-overlay" 
      :class="{ 'saving-locked': isSavingWorkflow }"
      @click.self="!isSavingWorkflow && (showWorkflowModal = false)"
    >
      <div class="modal-content glass-panel" :class="{ 'is-saving': isSavingWorkflow }">
        <div v-if="isSavingWorkflow" class="save-progress-container">
          <div class="save-progress-bar"><div class="save-progress-fill"></div></div>
          <span class="save-progress-text">Saving workflow to Pinecone...</span>
        </div>
        
        <h3>SAVE WORKFLOW TO PINECONE</h3>
        <div class="form-row">
          <div class="form-group half">
            <label>NAMESPACE</label>
            <select v-model="workflowForm.namespace" :disabled="isSavingWorkflow">
              <option value="test_execution_steps">Test Execution Steps</option>
              <option value="test_success_cases">Test Success Cases</option>
            </select>
          </div>
          <div class="form-group half">
            <label>INDEX</label>
            <select v-model="workflowForm.index" :disabled="isSavingWorkflow">
              <option value="steps-index">steps-index</option>
              <option value="hammer-index">hammer-index</option>
            </select>
          </div>
        </div>
        <div class="form-group">
          <label>GOALS TEXT (auto-filled from user prompts)</label>
          <textarea v-model="workflowForm.text" rows="3" readonly class="readonly-field" :disabled="isSavingWorkflow"></textarea>
        </div>
        <div class="modal-actions">
          <button class="btn secondary" @click="showWorkflowModal = false" :disabled="isSavingWorkflow">
            {{ isSavingWorkflow ? 'PLEASE WAIT...' : 'CANCEL' }}
          </button>
          <button class="btn primary" @click="submitWorkflow" :disabled="isSavingWorkflow">
            <span v-if="isSavingWorkflow" class="saving-spinner"></span>
            {{ isSavingWorkflow ? 'SAVING...' : 'SAVE' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Save Success Case Modal -->
    <div 
      v-if="showSuccessModal" 
      class="modal-overlay" 
      :class="{ 'saving-locked': isSavingSuccess }"
      @click.self="!isSavingSuccess && (showSuccessModal = false)"
    >
      <div class="modal-content glass-panel" :class="{ 'is-saving': isSavingSuccess }">
        <div v-if="isSavingSuccess" class="save-progress-container">
          <div class="save-progress-bar"><div class="save-progress-fill"></div></div>
          <span class="save-progress-text">Saving success case...</span>
        </div>
        
        <h3>SAVE SUCCESS CASE</h3>
        <div class="form-group">
          <label>GOAL TEXT</label>
          <input v-model="successForm.goal_text" type="text" placeholder="What was the user's goal?" :disabled="isSavingSuccess" />
        </div>
        <div class="form-group">
          <label>WORKFLOW NAME</label>
          <input v-model="successForm.workflow_name" type="text" placeholder="Name for this successful pattern" :disabled="isSavingSuccess" />
        </div>
        <div class="form-group">
          <label>COMPANY CONTEXT (optional)</label>
          <input v-model="successForm.company_context" type="text" placeholder="e.g. Graphi Connect, Client Portal" :disabled="isSavingSuccess" />
        </div>
        <div class="modal-actions">
          <button class="btn secondary" @click="showSuccessModal = false" :disabled="isSavingSuccess">
            {{ isSavingSuccess ? 'PLEASE WAIT...' : 'CANCEL' }}
          </button>
          <button class="btn primary" @click="submitSuccessCase" :disabled="isSavingSuccess">
            <span v-if="isSavingSuccess" class="saving-spinner"></span>
            {{ isSavingSuccess ? 'SAVING...' : 'SAVE' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Static Data Modal -->
    <div 
      v-if="showStaticDataModal" 
      class="modal-overlay" 
      :class="{ 'saving-locked': isSavingStaticData }"
      @click.self="!isSavingStaticData && (showStaticDataModal = false)"
    >
      <div class="modal-content glass-panel static-data-modal" :class="{ 'is-saving': isSavingStaticData }">
        <div v-if="isSavingStaticData" class="save-progress-container">
          <div class="save-progress-bar"><div class="save-progress-fill"></div></div>
          <span class="save-progress-text">Saving to static_data namespace...</span>
        </div>
        
        <h3>SAVE STATIC REFERENCE DATA</h3>
        <p class="static-data-description">Store valuable information that rarely changes (credentials, API keys, configuration values).</p>
        
        <div class="form-group">
          <label>DATA</label>
          <textarea 
            v-model="staticDataForm.data" 
            rows="6" 
            placeholder="Paste any important data here...&#10;Example: email: admin@test.com&#10;Example: API_KEY=sk-abc123..."
            :disabled="isSavingStaticData"
            :maxlength="MAX_STATIC_DATA_CHARS"
            class="static-data-textarea"
          ></textarea>
          <div class="char-counter" :class="{ 'near-limit': staticDataForm.data.length > MAX_STATIC_DATA_CHARS * 0.9 }">
            {{ staticDataForm.data.length }} / {{ MAX_STATIC_DATA_CHARS }} characters
          </div>
        </div>
        
        <div class="modal-actions">
          <button class="btn secondary" @click="showStaticDataModal = false" :disabled="isSavingStaticData">
            {{ isSavingStaticData ? 'PLEASE WAIT...' : 'CANCEL' }}
          </button>
          <button class="btn primary static-save" @click="submitStaticData" :disabled="isSavingStaticData || !staticDataForm.data.trim()">
            <span v-if="isSavingStaticData" class="saving-spinner"></span>
            {{ isSavingStaticData ? 'SAVING...' : 'SAVE' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Hammer Upload Modal -->
    <div 
      v-if="showHammerModal" 
      class="modal-overlay" 
      :class="{ 'saving-locked': isUploadingHammer }"
      @click.self="!isUploadingHammer && (showHammerModal = false)"
    >
      <div class="modal-content glass-panel hammer-modal" :class="{ 'is-saving': isUploadingHammer }">
        <div v-if="isUploadingHammer" class="save-progress-container">
          <div class="save-progress-bar"><div class="save-progress-fill"></div></div>
          <span class="save-progress-text">Downloading & Indexing Hammer (this may take 10-20s)...</span>
        </div>
        
        <h3>HAMMER CONFIGURATION</h3>
        <p class="static-data-description">Enter the Company ID or Name to automatically download and index the latest Hammer file from Graphite.</p>
        
        <div class="form-group">
          <label>COMPANY ID / NAME</label>
          <input 
            v-model="hammerForm.companyValue" 
            type="text" 
            placeholder="e.g. western, US66254, adobe" 
            :disabled="isUploadingHammer"
            @keydown.enter="submitHammerUpload"
          />
        </div>
        
        <div class="modal-actions">
           <button class="btn secondary" @click="showHammerModal = false" :disabled="isUploadingHammer">
            {{ isUploadingHammer ? 'PLEASE WAIT...' : 'CANCEL' }}
          </button>
          <button class="btn primary" @click="submitHammerUpload" :disabled="isUploadingHammer || !hammerForm.companyValue.trim()">
            <span v-if="isUploadingHammer" class="saving-spinner"></span>
            {{ isUploadingHammer ? 'INDEXING...' : 'START INDEXING' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Report Modal -->
    <div v-if="showReportModal" class="modal-overlay report-modal-overlay" @click.self="showReportModal = false">
      <div class="modal-content glass-panel report-modal">
        <div class="report-header">
          <h3>SESSION REPORT</h3>
          <div class="report-actions">
            <button class="btn secondary" @click="copyReportToClipboard" title="Copy to Clipboard">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
              COPY
            </button>
            <button class="btn secondary" @click="downloadReport" title="Download Report">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
              DOWNLOAD
            </button>
            <button class="btn secondary" @click="showReportModal = false">CLOSE</button>
          </div>
        </div>
        
        <div class="report-content">
          <!-- Session Info -->
          <div class="report-section">
            <h4>SESSION INFORMATION</h4>
            <div class="report-info-grid">
              <div class="info-item">
                <span class="info-label">Session ID</span>
                <span class="info-value">{{ sessionStore.currentTaskId || 'N/A' }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">Session Date</span>
                <span class="info-value">{{ sessionStore.sessionDate }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">Total Steps</span>
                <span class="info-value">{{ sessionStore.steps.length }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">Last Goal</span>
                <span class="info-value">{{ sessionStore.lastGoal || 'N/A' }}</span>
              </div>
            </div>
          </div>
          
          <!-- Mission Control -->
          <div class="report-section">
            <h4>MISSION CONTROL <span class="section-count">({{ sessionStore.messages.length }} messages)</span></h4>
            <div class="report-messages">
              <div v-for="msg in sessionStore.messages" :key="msg.id" class="report-message" :class="msg.role">
                <div class="message-meta">
                  <span class="message-role">{{ msg.role.toUpperCase() }}</span>
                  <span class="message-time">{{ msg.timestamp }}</span>
                </div>
                <div class="message-content">{{ msg.content }}</div>
              </div>
            </div>
          </div>
          
          <!-- System Logs -->
          <div class="report-section">
            <h4>SYSTEM LOGS <span class="section-count">({{ sessionStore.steps.length }} steps)</span></h4>
            <div class="report-steps">
              <div v-for="(step, index) in sessionStore.steps" :key="index" class="report-step">
                <div class="step-header">
                  <span class="step-number">STEP {{ index + 1 }}</span>
                  <span class="step-time">{{ step.timestamp }}</span>
                </div>
                <div class="step-details">
                  <div class="step-row" v-if="step.action">
                    <span class="step-label">Action:</span>
                    <span class="step-value">{{ step.action }}</span>
                  </div>
                  <div class="step-row" v-if="step.url">
                    <span class="step-label">URL:</span>
                    <span class="step-value url">{{ step.url }}</span>
                  </div>
                  <div class="step-row" v-if="step.reasoning">
                    <span class="step-label">Reasoning:</span>
                    <span class="step-value">{{ step.reasoning }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Image Viewer Modal -->
    <div v-if="zoomedImage" class="modal-overlay image-viewer" :class="{ 'dark-mode': uiStore.isDark }" @click="zoomedImage = null">
      <img :src="zoomedImage" alt="Screenshot" />
    </div>

    <!-- Toast -->
    <div v-if="uiStore.toast" class="toast" :class="uiStore.toast.type">
      {{ uiStore.toast.message }}
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import Background3D from '../components/Background3D.vue'
import ChatPanel from '../components/ChatPanel.vue'
import LiveView from '../components/LiveView.vue'
import StepLog from '../components/StepLog.vue'
import TheHeader from '../components/TheHeader.vue'
import { useUiStore } from '../stores/ui'
import { useAuthStore } from '../stores/auth'
import { useSessionStore } from '../stores/session'

const router = useRouter()
const uiStore = useUiStore()
const authStore = useAuthStore()
const sessionStore = useSessionStore()

// Constants
const MAX_STATIC_DATA_CHARS = 10000

// Local state (view-specific)
const zoomedImage = ref(null)

// Modal visibility
const showWorkflowModal = ref(false)
const showSuccessModal = ref(false)
const showStaticDataModal = ref(false)
const showHammerModal = ref(false)
const showReportModal = ref(false)

// Loading states
const isSavingWorkflow = ref(false)
const isSavingSuccess = ref(false)
const isSavingStaticData = ref(false)
const isUploadingHammer = ref(false)

// Hammer metadata for header
const hammerMetadata = ref(null)

// Form data
const workflowForm = ref({ namespace: 'test_execution_steps', index: 'steps-index', text: '' })
const successForm = ref({ goal_text: '', workflow_name: '', company_context: '' })
const staticDataForm = ref({ data: '' })
const hammerForm = ref({ companyValue: '' })

// ========== MODAL OPENERS ==========
function openWorkflowModal() {
  const allUserGoals = sessionStore.messages
    .filter(m => m.role === 'user')
    .map(m => m.content)
    .join('\n')
  
  workflowForm.value = { 
    namespace: 'test_execution_steps',
    index: 'steps-index',
    text: allUserGoals
  }
  showWorkflowModal.value = true
}

function openSuccessModal() {
  successForm.value = { 
    goal_text: sessionStore.lastGoal, 
    workflow_name: '', 
    company_context: '' 
  }
  showSuccessModal.value = true
}

function openStaticDataModal() {
  staticDataForm.value = { data: '' }
  showStaticDataModal.value = true
}

function openHammerModal() {
  hammerForm.value = { companyValue: '' }
  showHammerModal.value = true
}

function openReportModal() {
  showReportModal.value = true
}

// ========== SUBMIT HANDLERS ==========
async function submitWorkflow() {
  if (!sessionStore.currentTaskId) {
    uiStore.showToast('No active task to save', 'error')
    return
  }
  if (isSavingWorkflow.value) return
  isSavingWorkflow.value = true

  try {
    const urlsVisited = [...new Set(sessionStore.steps.map(s => s.url).filter(Boolean))]
    const actionsPerformed = sessionStore.steps.reduce((acc, step) => {
      const action = step.action_type || step.action || 'unknown'
      acc[action] = (acc[action] || 0) + 1
      return acc
    }, {})
    const stepsReferenceOnly = sessionStore.steps.map((s, i) => ({
      step: i + 1,
      timestamp: s.timestamp,
      url: s.url || null,
      reasoning: s.reasoning || null
    }))
    const userPrompts = sessionStore.messages.filter(m => m.role === 'user').map(m => m.content)

    const response = await fetch('http://localhost:8000/workflows/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        task_id: sessionStore.currentTaskId,
        name: 'workflow',
        description: '',
        namespace: workflowForm.value.namespace,
        index: workflowForm.value.index,
        text: workflowForm.value.text,
        urls_visited: urlsVisited,
        actions_performed: actionsPerformed,
        steps_reference_only: stepsReferenceOnly,
        user_prompts: userPrompts,
        tags: ['workflow'],
        steps: sessionStore.steps.map(s => { const { screenshot, ...rest } = s; return rest })
      })
    })

    if (response.ok) {
      uiStore.showToast('Workflow saved to Pinecone ✓', 'success')
      showWorkflowModal.value = false
    } else {
      const err = await response.json()
      uiStore.showToast(err.detail || 'Save failed', 'error')
    }
  } catch (e) {
    uiStore.showToast('Error: ' + e.message, 'error')
  } finally {
    isSavingWorkflow.value = false
  }
}

async function submitSuccessCase() {
  if (!successForm.value.goal_text || !successForm.value.workflow_name) {
    uiStore.showToast('Please fill goal and workflow name', 'error')
    return
  }
  if (isSavingSuccess.value) return
  isSavingSuccess.value = true

  try {
    const lastStep = sessionStore.steps[sessionStore.steps.length - 1]
    const response = await fetch('http://localhost:8000/success-cases', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        goal_text: successForm.value.goal_text,
        workflow_name: successForm.value.workflow_name,
        steps: sessionStore.steps.map(s => { const { screenshot, ...rest } = s; return rest }),
        final_url: lastStep?.url || '',
        company_context: successForm.value.company_context,
        session_id: sessionStore.currentTaskId || '',
        execution_time_ms: 0
      })
    })

    if (response.ok) {
      uiStore.showToast(`Success case saved: ${successForm.value.workflow_name}`, 'success')
      showSuccessModal.value = false
    } else {
      const err = await response.json()
      uiStore.showToast(err.detail || 'Save failed', 'error')
    }
  } catch (e) {
    uiStore.showToast('Error: ' + e.message, 'error')
  } finally {
    isSavingSuccess.value = false
  }
}

async function submitStaticData() {
  if (!staticDataForm.value.data.trim()) {
    uiStore.showToast('Data field cannot be empty', 'error')
    return
  }
  if (isSavingStaticData.value) return
  isSavingStaticData.value = true

  try {
    const response = await fetch('http://localhost:8000/static-data', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ data: staticDataForm.value.data })
    })

    if (response.ok) {
      const result = await response.json()
      uiStore.showToast(`Static data saved ✓ (${result.char_count} chars)`, 'success')
      showStaticDataModal.value = false
    } else {
      const err = await response.json()
      uiStore.showToast(err.detail || 'Save failed', 'error')
    }
  } catch (e) {
    uiStore.showToast('Error: ' + e.message, 'error')
  } finally {
    isSavingStaticData.value = false
  }
}

async function submitHammerUpload() {
  const company = hammerForm.value.companyValue.trim()
  if (!company) return
  if (isUploadingHammer.value) return
  isUploadingHammer.value = true
  
  try {
    const response = await fetch('http://localhost:8000/hammer/download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ company: company, clear_existing: true })
    })
    
    if (response.ok) {
      uiStore.showToast('Hammer file indexed successfully! ✓', 'success')
      showHammerModal.value = false
    } else {
      const err = await response.json()
      uiStore.showToast(err.detail || 'Download failed', 'error')
    }
  } catch (e) {
    uiStore.showToast('Error: ' + e.message, 'error')
  } finally {
    isUploadingHammer.value = false
    // Refresh hammer metadata after successful upload
    fetchHammerMetadata()
  }
}

// Fetch hammer metadata for header display
async function fetchHammerMetadata() {
  try {
    const token = authStore.idToken
    const headers = token ? { 'Authorization': `Bearer ${token}` } : {}
    
    const response = await fetch('http://localhost:8000/hammer/metadata', { headers })
    if (response.ok) {
      hammerMetadata.value = await response.json()
    }
  } catch (e) {
    console.error('Failed to fetch hammer metadata:', e)
  }
}

// ========== REPORT FUNCTIONS ==========
function generateReportText() {
  let report = '='.repeat(60) + '\nSESSION REPORT\n' + '='.repeat(60) + '\n\n'
  report += 'SESSION INFORMATION\n' + '-'.repeat(30) + '\n'
  report += `Session ID: ${sessionStore.currentTaskId || 'N/A'}\n`
  report += `Session Date: ${sessionStore.sessionDate}\n`
  report += `Total Steps: ${sessionStore.steps.length}\n`
  report += `Last Goal: ${sessionStore.lastGoal || 'N/A'}\n\n`
  
  report += 'MISSION CONTROL\n' + '-'.repeat(30) + '\n'
  sessionStore.messages.forEach(msg => {
    report += `[${msg.timestamp}] [${msg.role.toUpperCase()}] ${msg.content}\n\n`
  })
  
  report += 'SYSTEM LOGS\n' + '-'.repeat(30) + '\n'
  sessionStore.steps.forEach((step, index) => {
    report += `\n--- STEP ${index + 1} ---\n`
    report += `Timestamp: ${step.timestamp}\n`
    if (step.url) report += `URL: ${step.url}\n`
    if (step.reasoning) report += `Reasoning: ${step.reasoning}\n`
  })
  
  report += '\n' + '='.repeat(60) + '\nEND OF REPORT\n' + '='.repeat(60) + '\n'
  return report
}

function copyReportToClipboard() {
  navigator.clipboard.writeText(generateReportText()).then(() => {
    uiStore.showToast('Report copied to clipboard', 'success')
  }).catch(() => {
    uiStore.showToast('Failed to copy report', 'error')
  })
}

function downloadReport() {
  const blob = new Blob([generateReportText()], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `session-report-${sessionStore.currentTaskId || 'unknown'}-${new Date().toISOString().slice(0,10)}.txt`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
  uiStore.showToast('Report downloaded', 'success')
}

// ========== UTILITY ==========
function handleViewImage(url) {
  zoomedImage.value = url
}

function handleAvatarError(e) {
  e.target.src = 'data:image/svg+xml,' + encodeURIComponent(`
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40">
      <circle cx="20" cy="20" r="20" fill="#667eea"/>
      <text x="20" y="26" text-anchor="middle" fill="white" font-size="16" font-family="Arial">?</text>
    </svg>
  `)
}

async function handleLogout() {
  await authStore.logout()
  uiStore.showToast('Logged out successfully', 'info')
  router.push({ name: 'login' })
}

// ========== LIFECYCLE ==========
onMounted(() => {
  sessionStore.connect()
  fetchHammerMetadata()  // Fetch hammer metadata on mount
})

onUnmounted(() => {
  sessionStore.disconnect()
})
</script>

<style scoped>
/* Modal-specific styles that extend base App.vue styles */
.static-data-modal {
  border: 1px solid rgba(99, 102, 241, 0.3);
}

.static-data-description {
  font-size: 0.8rem;
  color: var(--text-muted);
  margin-bottom: 1rem;
}

.static-data-textarea {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem;
  line-height: 1.5;
}

.char-counter {
  font-size: 0.7rem;
  color: var(--text-muted);
  text-align: right;
  margin-top: 0.25rem;
}

.char-counter.near-limit {
  color: #f59e0b;
}

.btn.static-save {
  background: rgba(99, 102, 241, 0.2);
  border-color: rgba(99, 102, 241, 0.4);
  color: #818cf8;
}

.btn.static-save:hover:not(:disabled) {
  background: rgba(99, 102, 241, 0.3);
}

/* Report Modal */
.report-modal-overlay {
  z-index: 150;
}

.report-modal {
  width: 90%;
  max-width: 900px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.report-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--border-color);
  margin-bottom: 1rem;
}

.report-header h3 {
  font-size: 0.9rem;
  letter-spacing: 2px;
  color: var(--text-primary);
  margin: 0;
}

.report-actions {
  display: flex;
  gap: 0.5rem;
}

.report-actions .btn {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.report-content {
  flex: 1;
  overflow-y: auto;
  padding-right: 0.5rem;
}

.report-section {
  margin-bottom: 1.5rem;
}

.report-section h4 {
  font-size: 0.7rem;
  letter-spacing: 1.5px;
  color: var(--text-primary);
  margin-bottom: 0.75rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border-color);
}

.report-section h4 .section-count {
  color: var(--text-muted);
  font-weight: 400;
}

.report-info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.75rem;
}

.info-item {
  background: var(--bg-primary);
  padding: 0.75rem;
  border-radius: 8px;
  border: 1px solid var(--border-color);
}

.info-label {
  display: block;
  font-size: 0.6rem;
  letter-spacing: 1px;
  color: var(--text-muted);
  text-transform: uppercase;
  margin-bottom: 0.25rem;
}

.info-value {
  font-size: 0.85rem;
  color: var(--text-primary);
  font-family: 'JetBrains Mono', monospace;
  word-break: break-all;
}

.report-messages, .report-steps {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.report-message, .report-step {
  background: var(--bg-primary);
  padding: 0.75rem;
  border-radius: 8px;
  border: 1px solid var(--border-color);
}

.report-message.user { border-left: 3px solid #818cf8; }
.report-message.agent { border-left: 3px solid var(--success); }
.report-message.system { border-left: 3px solid var(--text-muted); }

.message-meta, .step-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.5rem;
}

.message-role, .step-number {
  font-size: 0.6rem;
  letter-spacing: 1px;
  font-weight: 600;
}

.step-number { color: #818cf8; }

.message-time, .step-time {
  font-size: 0.6rem;
  color: var(--text-muted);
  font-family: 'JetBrains Mono', monospace;
}

.message-content {
  font-size: 0.85rem;
  color: var(--text-primary);
  line-height: 1.5;
  white-space: pre-wrap;
}

.step-details {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.step-row {
  display: flex;
  gap: 0.5rem;
}

.step-label {
  font-size: 0.7rem;
  color: var(--text-muted);
  min-width: 80px;
  text-transform: uppercase;
}

.step-value {
  font-size: 0.8rem;
  color: var(--text-primary);
  flex: 1;
  word-break: break-word;
}

.step-value.url {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  color: var(--text-secondary);
}

/* Save Progress */
.save-progress-container {
  margin-bottom: 1rem;
  text-align: center;
}

.save-progress-bar {
  height: 4px;
  background: var(--bg-tertiary);
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 0.5rem;
}

.save-progress-fill {
  height: 100%;
  width: 30%;
  background: linear-gradient(90deg, var(--success), #22d3ee, var(--success));
  background-size: 200% 100%;
  border-radius: 4px;
  animation: progressFlow 1.5s ease-in-out infinite;
}

@keyframes progressFlow {
  0% { transform: translateX(-100%); background-position: 0% 0%; }
  50% { background-position: 100% 0%; }
  100% { transform: translateX(400%); background-position: 0% 0%; }
}

.save-progress-text {
  font-size: 0.7rem;
  color: var(--text-muted);
  letter-spacing: 1px;
  text-transform: uppercase;
}

.saving-spinner {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid var(--bg-primary);
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-right: 6px;
  vertical-align: middle;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Hammer Modal */
.hammer-modal {
  max-width: 500px !important;
}

.hammer-modal h3 {
  color: #ec4899 !important;
  border-bottom-color: rgba(236, 72, 153, 0.3) !important;
}

/* Saving states */
.modal-overlay.saving-locked {
  cursor: not-allowed;
}

.modal-content.is-saving {
  position: relative;
  pointer-events: none;
}

.modal-content.is-saving::after {
  content: '';
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.2);
  border-radius: inherit;
  pointer-events: all;
}

.modal-content.is-saving .modal-actions {
  pointer-events: all;
  position: relative;
  z-index: 10;
}
</style>
