<template>
  <Background3D :is-dark="isDark" />

  <div class="hud-container" :class="{ 'light-mode': !isDark }">
    <!-- Header -->
    <header class="glass-header">
      <div class="logo-area">
        <span class="status-dot" :class="connectionStatusClass"></span>
        <h1>Configuration Specialist Agent</h1>
      </div>
      <div class="controls">
        <!-- Theme Toggle -->
        <button 
          class="control-btn icon-btn" 
          @click="toggleTheme"
          :title="isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode'"
        >
          <!-- Sun icon for dark mode (click to go light) -->
          <svg v-if="isDark" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="5"></circle>
            <line x1="12" y1="1" x2="12" y2="3"></line>
            <line x1="12" y1="21" x2="12" y2="23"></line>
            <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
            <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
            <line x1="1" y1="12" x2="3" y2="12"></line>
            <line x1="21" y1="12" x2="23" y2="12"></line>
            <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
            <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
          </svg>
          <!-- Moon icon for light mode (click to go dark) -->
          <svg v-else xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
          </svg>
        </button>

        <!-- Close Browser -->
        <button 
          v-if="hasBrowser && !isRunning" 
          class="control-btn icon-btn" 
          @click="closeBrowser"
          title="Close Browser"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>

        <!-- Save Workflow -->
        <button 
          v-if="steps.length > 0 && !isRunning" 
          class="control-btn" 
          @click="openSaveModal('workflow')"
          title="Save Workflow"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
          SAVE
        </button>

        <!-- Report Button -->
        <button 
          v-if="steps.length > 0 && !isRunning" 
          class="control-btn report" 
          @click="openReportModal"
          title="Generate Session Report"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
          REPORT
        </button>

        <!-- Save Success Case -->
        <button 
          v-if="steps.length > 0 && !isRunning" 
          class="control-btn success" 
          @click="openSaveModal('success')"
          title="Save Success Case"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
          SUCCESS
        </button>
        
        <!-- End Session -->
        <button 
          v-if="steps.length > 0" 
          class="control-btn danger" 
          @click="endSession"
          title="End Session"
        >
          END
        </button>
      </div>
    </header>

    <!-- Main Grid -->
    <main class="main-grid">
      <!-- Left: Mission Control (Chat) -->
      <section class="glass-panel control-panel">
        <h2>MISSION CONTROL</h2>
        <ChatPanel 
          :messages="messages" 
          :status="taskStatus"
          :is-dark="isDark"
          @send-message="handleSendMessage" 
          @stop="stopTask"
        />
      </section>

      <!-- Center: Viewport (Live View) -->
      <section class="viewport-panel">
        <LiveView 
          :screenshot="currentScreenshot" 
          :status="taskStatus"
          :is-dark="isDark"
        />
      </section>

      <!-- Right: System Logs (Steps) -->
      <section class="glass-panel logs-panel">
        <h2>SYSTEM LOGS <span class="count" v-if="steps.length">({{ steps.length }})</span></h2>
        <StepLog :steps="steps" :is-dark="isDark" @view-image="handleViewImage" />
      </section>
    </main>

    <!-- Save Workflow Modal -->
    <div v-if="showSaveModal && saveModalType === 'workflow'" class="modal-overlay" @click.self="closeSaveModal">
      <div class="modal-content glass-panel">
        <h3>SAVE WORKFLOW</h3>
        <div class="form-group">
          <label>NAME</label>
          <input v-model="workflowForm.name" type="text" placeholder="e.g. Login to Dashboard" />
        </div>
        <div class="form-group">
          <label>DESCRIPTION</label>
          <textarea v-model="workflowForm.description" rows="3" placeholder="What does this workflow accomplish?"></textarea>
        </div>
        <div class="modal-actions">
          <button class="btn secondary" @click="closeSaveModal">CANCEL</button>
          <button class="btn primary" @click="submitWorkflow">SAVE</button>
        </div>
      </div>
    </div>

    <!-- Save Success Case Modal -->
    <div v-if="showSaveModal && saveModalType === 'success'" class="modal-overlay" @click.self="closeSaveModal">
      <div class="modal-content glass-panel">
        <h3>SAVE SUCCESS CASE</h3>
        <div class="form-group">
          <label>GOAL TEXT</label>
          <input v-model="successForm.goal_text" type="text" placeholder="What was the user's goal?" />
        </div>
        <div class="form-group">
          <label>WORKFLOW NAME</label>
          <input v-model="successForm.workflow_name" type="text" placeholder="Name for this successful pattern" />
        </div>
        <div class="form-group">
          <label>COMPANY CONTEXT (optional)</label>
          <input v-model="successForm.company_context" type="text" placeholder="e.g. Graphi Connect, Client Portal" />
        </div>
        <div class="modal-actions">
          <button class="btn secondary" @click="closeSaveModal">CANCEL</button>
          <button class="btn primary" @click="submitSuccessCase">SAVE</button>
        </div>
      </div>
    </div>

    <!-- Report Modal -->
    <div v-if="showReportModal" class="modal-overlay report-modal-overlay" @click.self="closeReportModal">
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
            <button class="btn secondary" @click="closeReportModal">CLOSE</button>
          </div>
        </div>
        
        <div class="report-content">
          <!-- Session Info -->
          <div class="report-section">
            <h4>SESSION INFORMATION</h4>
            <div class="report-info-grid">
              <div class="info-item">
                <span class="info-label">Session ID</span>
                <span class="info-value">{{ currentTaskId || 'N/A' }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">Session Date</span>
                <span class="info-value">{{ sessionDate }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">Total Steps</span>
                <span class="info-value">{{ steps.length }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">Last Goal</span>
                <span class="info-value">{{ lastGoal || 'N/A' }}</span>
              </div>
            </div>
          </div>
          
          <!-- Mission Control -->
          <div class="report-section">
            <h4>MISSION CONTROL <span class="section-count">({{ messages.length }} messages)</span></h4>
            <div class="report-messages">
              <div 
                v-for="msg in messages" 
                :key="msg.id" 
                class="report-message"
                :class="msg.role"
              >
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
            <h4>SYSTEM LOGS <span class="section-count">({{ steps.length }} steps)</span></h4>
            <div class="report-steps">
              <div 
                v-for="(step, index) in steps" 
                :key="index" 
                class="report-step"
              >
                <div class="step-header">
                  <span class="step-number">STEP {{ index + 1 }}</span>
                  <span class="step-time">{{ step.timestamp }}</span>
                  <span class="step-id" v-if="step.step_id">ID: {{ step.step_id }}</span>
                </div>
                <div class="step-details">
                  <div class="step-row" v-if="step.action">
                    <span class="step-label">Action:</span>
                    <span class="step-value">{{ step.action }}</span>
                  </div>
                  <div class="step-row" v-if="step.target">
                    <span class="step-label">Target:</span>
                    <span class="step-value">{{ step.target }}</span>
                  </div>
                  <div class="step-row" v-if="step.description">
                    <span class="step-label">Description:</span>
                    <span class="step-value">{{ step.description }}</span>
                  </div>
                  <div class="step-row" v-if="step.value">
                    <span class="step-label">Value:</span>
                    <span class="step-value">{{ step.value }}</span>
                  </div>
                  <div class="step-row" v-if="step.url">
                    <span class="step-label">URL:</span>
                    <span class="step-value url">{{ step.url }}</span>
                  </div>
                  <div class="step-row" v-if="step.reasoning">
                    <span class="step-label">Reasoning:</span>
                    <span class="step-value">{{ step.reasoning }}</span>
                  </div>
                  <div class="step-row" v-if="step.goal_id">
                    <span class="step-label">Goal ID:</span>
                    <span class="step-value">{{ step.goal_id }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Image Viewer Modal -->
    <div v-if="zoomedImage" class="modal-overlay image-viewer" @click="zoomedImage = null">
      <img :src="zoomedImage" alt="Screenshot" />
    </div>

    <!-- Toast -->
    <div v-if="toast" class="toast" :class="toast.type">
      {{ toast.message }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import Background3D from './components/Background3D.vue'
import ChatPanel from './components/ChatPanel.vue'
import LiveView from './components/LiveView.vue'
import StepLog from './components/StepLog.vue'

// State
const messages = ref([])
const steps = ref([])
const allScreenshots = ref([])
const currentScreenshot = ref(null)
const isConnected = ref(false)
const taskStatus = ref('idle')
const currentTaskId = ref(null)
const toast = ref(null)
const hasBrowser = ref(false)
const zoomedImage = ref(null)
const isDark = ref(true)
const lastGoal = ref('')

// Save Modal State
const showSaveModal = ref(false)
const saveModalType = ref('workflow') // 'workflow' | 'success'
const workflowForm = ref({ name: '', description: '' })
const successForm = ref({ goal_text: '', workflow_name: '', company_context: '' })

// Report Modal State
const showReportModal = ref(false)
const sessionDate = ref(new Date().toLocaleString())

let websocket = null

// Computed
const isRunning = computed(() => taskStatus.value === 'running' || taskStatus.value === 'starting')

const connectionStatusClass = computed(() => ({
  'connected': isConnected.value && !isRunning.value,
  'running': isRunning.value,
  'disconnected': !isConnected.value
}))

// Theme Toggle
function toggleTheme() {
  isDark.value = !isDark.value
  localStorage.setItem('theme', isDark.value ? 'dark' : 'light')
}

// Toast
function showToast(message, type = 'info') {
  toast.value = { message, type }
  setTimeout(() => toast.value = null, 3000)
}

// WebSocket
function connectWebSocket() {
  websocket = new WebSocket('ws://localhost:8000/ws/agent')

  websocket.onopen = () => {
    isConnected.value = true
    addMessage('system', 'Connection established. Ready for commands.')
  }

  websocket.onclose = () => {
    isConnected.value = false
    taskStatus.value = 'idle'
    addMessage('system', 'Connection lost. Reconnecting...')
    setTimeout(connectWebSocket, 3000)
  }

  websocket.onerror = (error) => {
    console.error('WebSocket error:', error)
  }

  websocket.onmessage = (event) => {
    const data = JSON.parse(event.data)
    handleServerMessage(data)
  }
}

function handleServerMessage(data) {
  switch (data.type) {
    case 'status':
      taskStatus.value = data.status
      if (data.task_id) currentTaskId.value = data.task_id
      if (data.message) addMessage('agent', data.message)
      
      if (data.status === 'running' || data.status === 'starting') {
        hasBrowser.value = true
      }
      if (data.message === 'Browser closed') {
        hasBrowser.value = false
      }
      break

    case 'step':
      const stepData = {
        ...data.step,
        screenshot: data.screenshot ? `data:image/png;base64,${data.screenshot}` : null,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
      }
      steps.value.push(stepData)
      
      if (data.screenshot) {
        const screenshotUrl = `data:image/png;base64,${data.screenshot}`
        currentScreenshot.value = screenshotUrl
        allScreenshots.value.push(screenshotUrl)
      }
      break

    case 'completed':
      taskStatus.value = 'idle'
      addMessage('agent', `**Mission Complete.** Executed ${data.step_count} steps successfully.`)
      break

    case 'error':
      taskStatus.value = 'idle'
      addMessage('agent', `**Error:** ${data.message}`)
      break

    case 'workflow_saved':
      showToast(`Saved: ${data.name}`, 'success')
      break
  }
}

function addMessage(role, content) {
  messages.value.push({
    id: Date.now(),
    role,
    content,
    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  })
}

function handleSendMessage(goal) {
  if (!goal.trim() || !isConnected.value || isRunning.value) return

  lastGoal.value = goal
  addMessage('user', goal)

  const stepOffset = steps.value.length

  websocket.send(JSON.stringify({
    type: 'start',
    goal: goal,
    start_url: '',
    step_offset: stepOffset
  }))
  
  hasBrowser.value = true
}

function stopTask() {
  if (websocket && isRunning.value) {
    websocket.send(JSON.stringify({ type: 'stop' }))
  }
}

function closeBrowser() {
  if (websocket && !isRunning.value && hasBrowser.value) {
    websocket.send(JSON.stringify({ type: 'close_browser' }))
    hasBrowser.value = false
    showToast('Browser closed', 'info')
  }
}

function endSession() {
  if (websocket) {
    websocket.send(JSON.stringify({ type: 'end_session' }))
  }
  
  steps.value = []
  allScreenshots.value = []
  currentScreenshot.value = null
  hasBrowser.value = false
  currentTaskId.value = null
  taskStatus.value = 'idle'
  lastGoal.value = ''
  
  showToast('Session ended', 'info')
  addMessage('system', 'Session terminated. Memory cleared.')
}

function handleViewImage(url) {
  zoomedImage.value = url
}

// Save Modal
function openSaveModal(type) {
  saveModalType.value = type
  showSaveModal.value = true
  
  if (type === 'workflow') {
    workflowForm.value = { name: '', description: '' }
  } else {
    // Pre-fill with last goal
    successForm.value = { 
      goal_text: lastGoal.value, 
      workflow_name: '', 
      company_context: '' 
    }
  }
}

function closeSaveModal() {
  showSaveModal.value = false
}

// Save Workflow
async function submitWorkflow() {
  if (!currentTaskId.value || !workflowForm.value.name) {
    showToast('Please provide a name', 'error')
    return
  }

  try {
    const response = await fetch('http://localhost:8000/workflows/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        task_id: currentTaskId.value,
        name: workflowForm.value.name,
        description: workflowForm.value.description,
        tags: ['workflow'],
        steps: steps.value.map(s => {
          const { screenshot, ...rest } = s
          return rest
        })
      })
    })

    if (response.ok) {
      showToast(`Workflow saved: ${workflowForm.value.name}`, 'success')
      closeSaveModal()
    } else {
      const err = await response.json()
      showToast(err.detail || 'Save failed', 'error')
    }
  } catch (e) {
    showToast('Error: ' + e.message, 'error')
  }
}

// Save Success Case
async function submitSuccessCase() {
  if (!successForm.value.goal_text || !successForm.value.workflow_name) {
    showToast('Please fill goal and workflow name', 'error')
    return
  }

  try {
    const lastStep = steps.value[steps.value.length - 1]
    const response = await fetch('http://localhost:8000/success-cases', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        goal_text: successForm.value.goal_text,
        workflow_name: successForm.value.workflow_name,
        steps: steps.value.map(s => {
          const { screenshot, ...rest } = s
          return rest
        }),
        final_url: lastStep?.url || '',
        company_context: successForm.value.company_context,
        session_id: currentTaskId.value || '',
        execution_time_ms: 0
      })
    })

    if (response.ok) {
      showToast(`Success case saved: ${successForm.value.workflow_name}`, 'success')
      closeSaveModal()
    } else {
      const err = await response.json()
      showToast(err.detail || 'Save failed', 'error')
    }
  } catch (e) {
    showToast('Error: ' + e.message, 'error')
  }
}

// Report Modal Functions
function openReportModal() {
  sessionDate.value = new Date().toLocaleString()
  showReportModal.value = true
}

function closeReportModal() {
  showReportModal.value = false
}

function generateReportText() {
  let report = ''
  
  // Header
  report += '='.repeat(60) + '\n'
  report += 'SESSION REPORT\n'
  report += '='.repeat(60) + '\n\n'
  
  // Session Information
  report += 'SESSION INFORMATION\n'
  report += '-'.repeat(30) + '\n'
  report += `Session ID: ${currentTaskId.value || 'N/A'}\n`
  report += `Session Date: ${sessionDate.value}\n`
  report += `Total Steps: ${steps.value.length}\n`
  report += `Last Goal: ${lastGoal.value || 'N/A'}\n\n`
  
  // Execution Summary (NEW - High-level summary of what happened)
  report += 'EXECUTION SUMMARY\n'
  report += '-'.repeat(30) + '\n'
  
  // Extract key URLs visited
  const urlsVisited = [...new Set(steps.value.map(s => s.url).filter(Boolean))]
  if (urlsVisited.length > 0) {
    report += `URLs Visited: ${urlsVisited.length}\n`
    urlsVisited.forEach((url, i) => {
      report += `  ${i + 1}. ${url}\n`
    })
  }
  
  // Extract action types summary
  const actionCounts = steps.value.reduce((acc, step) => {
    const action = step.action_type || step.action || 'unknown'
    acc[action] = (acc[action] || 0) + 1
    return acc
  }, {})
  
  report += `\nActions Performed:\n`
  Object.entries(actionCounts).forEach(([action, count]) => {
    report += `  - ${action}: ${count} time(s)\n`
  })
  
  // Determine final status
  const lastMessage = messages.value[messages.value.length - 1]
  const finalStatus = lastMessage?.content?.includes('Complete') ? 'SUCCESS' : 
                      lastMessage?.content?.includes('Error') ? 'FAILED' : 'COMPLETED'
  report += `\nFinal Status: ${finalStatus}\n\n`
  
  // Mission Control - Strategic Messages Only (filtered)
  report += 'MISSION CONTROL (Strategic Events)\n'
  report += '-'.repeat(30) + '\n'
  
  // Filter messages to show only strategic/meaningful ones
  const strategicMessages = messages.value.filter(msg => {
    const content = msg.content.toLowerCase()
    // Skip low-level execution messages
    if (content.startsWith('executing:')) return false
    if (content.startsWith('thinking:')) return false
    // Keep system messages
    if (msg.role === 'system') return true
    // Keep user messages
    if (msg.role === 'user') return true
    // Keep meaningful agent messages
    if (content.includes('complete') || content.includes('error') || 
        content.includes('starting') || content.includes('subtask') ||
        content.includes('decomposed') || content.includes('success') ||
        content.includes('failed') || content.includes('navigating') ||
        content.includes('loading') || content.includes('credentials') ||
        content.includes('submitting') || content.includes('changing') ||
        content.includes('safety') || msg.content.length > 100) return true
    return false
  })
  
  strategicMessages.forEach(msg => {
    const roleLabel = msg.role === 'system' ? 'SYS' : 
                      msg.role === 'user' ? 'USR' : 'AGT'
    report += `[${msg.timestamp}] [${roleLabel}] ${msg.content}\n\n`
  })
  
  // System Logs - Full Technical Details
  report += '\nSYSTEM LOGS (Technical Details)\n'
  report += '-'.repeat(30) + '\n'
  steps.value.forEach((step, index) => {
    report += `\n--- STEP ${index + 1} ---\n`
    report += `Timestamp: ${step.timestamp}\n`
    if (step.url) report += `URL: ${step.url}\n`
    if (step.reasoning) report += `Reasoning: ${step.reasoning}\n`
  })
  
  report += '\n' + '='.repeat(60) + '\n'
  report += 'END OF REPORT\n'
  report += '='.repeat(60) + '\n'
  
  return report
}

function copyReportToClipboard() {
  const reportText = generateReportText()
  navigator.clipboard.writeText(reportText).then(() => {
    showToast('Report copied to clipboard', 'success')
  }).catch(() => {
    showToast('Failed to copy report', 'error')
  })
}

function downloadReport() {
  const reportText = generateReportText()
  const blob = new Blob([reportText], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `session-report-${currentTaskId.value || 'unknown'}-${new Date().toISOString().slice(0,10)}.txt`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
  showToast('Report downloaded', 'success')
}

// Lifecycle
onMounted(() => {
  // Load saved theme preference
  const savedTheme = localStorage.getItem('theme')
  if (savedTheme) {
    isDark.value = savedTheme === 'dark'
  }
  
  connectWebSocket()
})

onUnmounted(() => {
  if (websocket) websocket.close()
})
</script>

<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

/* ========================================
   GRAYSCALE THEME - DARK & LIGHT MODES
   ======================================== */

:root {
  /* Dark Mode (Default) */
  --bg-primary: #0a0a0a;
  --bg-secondary: #141414;
  --bg-tertiary: #1a1a1a;
  --text-primary: #ffffff;
  --text-secondary: #a0a0a0;
  --text-muted: #666666;
  --border-color: rgba(255, 255, 255, 0.1);
  --border-strong: rgba(255, 255, 255, 0.2);
  --accent: #ffffff;
  --success: #10b981;
  --danger: #ef4444;
  --glass-bg: rgba(20, 20, 20, 0.8);
}

.light-mode {
  --bg-primary: #ffffff;
  --bg-secondary: #f5f5f5;
  --bg-tertiary: #ebebeb;
  --text-primary: #0a0a0a;
  --text-secondary: #555555;
  --text-muted: #888888;
  --border-color: rgba(0, 0, 0, 0.1);
  --border-strong: rgba(0, 0, 0, 0.2);
  --accent: #0a0a0a;
  --success: #059669;
  --danger: #dc2626;
  --glass-bg: rgba(255, 255, 255, 0.85);
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  background-color: var(--bg-primary);
  color: var(--text-primary);
  font-family: 'Inter', system-ui, sans-serif;
  overflow: hidden;
  -webkit-font-smoothing: antialiased;
}

/* HUD Container */
.hud-container {
  position: relative;
  z-index: 10;
  height: 100vh;
  display: flex;
  flex-direction: column;
  padding: 1rem;
}

/* Glass Header */
.glass-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1.5rem;
  background: var(--glass-bg);
  backdrop-filter: blur(12px);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  margin-bottom: 1rem;
}

.logo-area {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.logo-area h1 {
  font-size: 0.95rem;
  font-weight: 600;
  letter-spacing: 0.5px;
  color: var(--text-primary);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-muted);
  transition: all 0.3s;
}

.status-dot.connected {
  background: var(--success);
  box-shadow: 0 0 8px var(--success);
}

.status-dot.running {
  background: var(--text-primary);
  box-shadow: 0 0 12px var(--text-primary);
  animation: pulse 1s infinite;
}

.status-dot.disconnected {
  background: var(--danger);
}

@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.2); opacity: 0.7; }
}

.controls {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.control-btn {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.5rem 0.75rem;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  color: var(--text-secondary);
  font-size: 0.65rem;
  font-weight: 600;
  letter-spacing: 1px;
  cursor: pointer;
  transition: all 0.2s;
}

.control-btn:hover {
  background: var(--border-strong);
  color: var(--text-primary);
}

.control-btn.icon-btn {
  padding: 0.5rem;
}

.control-btn.success {
  background: rgba(16, 185, 129, 0.1);
  border-color: rgba(16, 185, 129, 0.3);
  color: var(--success);
}

.control-btn.success:hover {
  background: rgba(16, 185, 129, 0.2);
}

.control-btn.danger {
  background: rgba(239, 68, 68, 0.1);
  border-color: rgba(239, 68, 68, 0.3);
  color: var(--danger);
}

.control-btn.danger:hover {
  background: rgba(239, 68, 68, 0.2);
}

/* Main Grid */
.main-grid {
  display: grid;
  grid-template-columns: 320px 1fr 280px;
  gap: 1rem;
  flex: 1;
  min-height: 0;
}

/* Glass Panels */
.glass-panel {
  background: var(--glass-bg);
  backdrop-filter: blur(15px);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.glass-panel h2 {
  font-size: 0.65rem;
  color: var(--text-secondary);
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 0.5rem;
  margin-bottom: 0.75rem;
  letter-spacing: 2px;
  font-weight: 600;
  text-transform: uppercase;
}

.glass-panel h2 .count {
  color: var(--text-muted);
  font-weight: 400;
}

.control-panel, .logs-panel {
  min-height: 0;
}

/* Viewport Panel */
.viewport-panel {
  position: relative;
  border: 1px solid var(--border-strong);
  border-radius: 12px;
  overflow: hidden;
  background: var(--bg-primary);
}

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.modal-content {
  width: 100%;
  max-width: 420px;
  padding: 1.5rem;
}

.modal-content h3 {
  font-size: 0.8rem;
  letter-spacing: 2px;
  color: var(--text-primary);
  margin-bottom: 1.5rem;
  text-transform: uppercase;
}

.form-group {
  margin-bottom: 1rem;
}

.form-group label {
  display: block;
  font-size: 0.65rem;
  letter-spacing: 1px;
  color: var(--text-muted);
  margin-bottom: 0.5rem;
  text-transform: uppercase;
}

.form-group input,
.form-group textarea {
  width: 100%;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 0.75rem;
  color: var(--text-primary);
  font-size: 0.9rem;
  font-family: inherit;
  outline: none;
  transition: all 0.2s;
}

.form-group input:focus,
.form-group textarea:focus {
  border-color: var(--text-primary);
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  margin-top: 1.5rem;
}

.btn {
  padding: 0.6rem 1.25rem;
  border-radius: 8px;
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 1px;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
  text-transform: uppercase;
}

.btn.secondary {
  background: transparent;
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
}

.btn.secondary:hover {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.btn.primary {
  background: var(--text-primary);
  color: var(--bg-primary);
}

.btn.primary:hover {
  opacity: 0.9;
}

/* Image Viewer */
.image-viewer img {
  max-width: 90vw;
  max-height: 90vh;
  border-radius: 8px;
  box-shadow: 0 0 50px rgba(0, 0, 0, 0.5);
}

/* Toast */
.toast {
  position: fixed;
  bottom: 2rem;
  right: 2rem;
  padding: 0.75rem 1.5rem;
  background: var(--glass-bg);
  backdrop-filter: blur(10px);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  font-size: 0.85rem;
  color: var(--text-primary);
  z-index: 200;
  animation: slideUp 0.3s ease-out;
}

.toast.success {
  border-color: rgba(16, 185, 129, 0.5);
  color: var(--success);
}

.toast.error {
  border-color: rgba(239, 68, 68, 0.5);
  color: var(--danger);
}

.toast.info {
  border-color: var(--border-strong);
}

@keyframes slideUp {
  from { transform: translateY(20px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

/* Scrollbars */
::-webkit-scrollbar {
  width: 5px;
  height: 5px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: var(--border-strong);
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: var(--text-muted);
}

/* Report Button Style */
.control-btn.report {
  background: rgba(99, 102, 241, 0.1);
  border-color: rgba(99, 102, 241, 0.3);
  color: #818cf8;
}

.control-btn.report:hover {
  background: rgba(99, 102, 241, 0.2);
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

.report-messages {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.report-message {
  background: var(--bg-primary);
  padding: 0.75rem;
  border-radius: 8px;
  border: 1px solid var(--border-color);
}

.report-message.user {
  border-left: 3px solid #818cf8;
}

.report-message.agent {
  border-left: 3px solid var(--success);
}

.report-message.system {
  border-left: 3px solid var(--text-muted);
}

.message-meta {
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.5rem;
}

.message-role {
  font-size: 0.6rem;
  letter-spacing: 1px;
  color: var(--text-muted);
  font-weight: 600;
}

.message-time {
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

.report-steps {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.report-step {
  background: var(--bg-primary);
  padding: 0.75rem;
  border-radius: 8px;
  border: 1px solid var(--border-color);
}

.step-header {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 0.75rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border-color);
}

.step-number {
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 1px;
  color: #818cf8;
}

.step-time {
  font-size: 0.65rem;
  color: var(--text-muted);
  font-family: 'JetBrains Mono', monospace;
}

.step-id {
  font-size: 0.6rem;
  color: var(--text-muted);
  font-family: 'JetBrains Mono', monospace;
  margin-left: auto;
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
  letter-spacing: 0.5px;
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
</style>
