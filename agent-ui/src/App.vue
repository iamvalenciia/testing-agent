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
</style>
