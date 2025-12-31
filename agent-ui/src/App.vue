<template>
  <div id="app">
    <!-- Header -->
    <header class="app-header">
      <h1>Visual Apprentice</h1>
      


      <div class="status-indicator">
        <span 
          class="status-dot" 
          :class="{ connected: isConnected, running: isRunning }"
        ></span>
        <span>{{ statusText }}</span>
      </div>
    </header>

    <!-- Main Content -->
    <main class="main-content">
      <!-- Left: Chat Panel -->
      <ChatPanel
        :messages="messages"
        :is-running="isRunning"
        @send-message="handleSendMessage"
      />

      <!-- Right Panel -->
      <div class="right-panel">
        <!-- Top Right: Live View with all screenshots -->
        <LiveView 
          :screenshot="currentScreenshot" 
          :screenshots="allScreenshots"
          :is-running="isRunning" 
        />

        <!-- Bottom Right: Step Log -->
        <StepLog 
          :steps="steps" 
          :messages="messages"
          :is-running="isRunning"
          :task-id="currentTaskId"
          :has-browser="hasBrowser"
          @save-workflow="handleSaveWorkflow"
          @stop-task="stopTask"
          @close-browser="closeBrowser"
          @end-session="endSession"
        />
      </div>
    </main>

    <!-- Toast Notifications -->
    <div v-if="toast" class="toast" :class="toast.type">
      {{ toast.message }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
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

let websocket = null

// Computed
const isRunning = computed(() => taskStatus.value === 'running')

const statusText = computed(() => {
  if (!isConnected.value) return 'Disconnected'
  if (isRunning.value) return 'Running...'
  return 'Connected'
})

// Toast notifications
function showToast(message, type = 'info') {
  toast.value = { message, type }
  setTimeout(() => {
    toast.value = null
  }, 3000)
}

// WebSocket Connection
function connectWebSocket() {
  websocket = new WebSocket('ws://localhost:8000/ws/agent')

  websocket.onopen = () => {
    isConnected.value = true
    addMessage('system', 'Connected to backend')
  }

  websocket.onclose = () => {
    isConnected.value = false
    taskStatus.value = 'idle'
    addMessage('system', 'Disconnected')
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
      
      // Track browser state
      if (data.status === 'running' || data.status === 'starting') {
        hasBrowser.value = true
      }
      if (data.message === 'Browser closed') {
        hasBrowser.value = false
      }
      break

    case 'step':
      steps.value.push(data.step)
      if (data.screenshot) {
        const screenshotUrl = `data:image/png;base64,${data.screenshot}`
        currentScreenshot.value = screenshotUrl
        allScreenshots.value.push(screenshotUrl)
      }
      break

    case 'completed':
      taskStatus.value = 'idle'
      addMessage('agent', `Task completed (${data.step_count} steps)`)
      break

    case 'error':
      taskStatus.value = 'idle'
      addMessage('agent', `Error: ${data.message}`)
      break

    case 'workflow_saved':
      showToast(`Workflow "${data.name}" saved!`, 'success')
      break

    case 'pong':
      break
  }
}

function addMessage(role, content) {
  messages.value.push({
    id: Date.now(),
    role,
    content,
    timestamp: new Date().toLocaleTimeString()
  })
}

function handleSendMessage(goal) {
  if (!goal.trim() || !isConnected.value || isRunning.value) return

  addMessage('user', goal)

  // DON'T clear steps/screenshots - accumulate them across prompts
  // Only clear when user explicitly ends the session
  
  // Calculate step offset for numbering
  const stepOffset = steps.value.length

  websocket.send(JSON.stringify({
    type: 'start',
    goal: goal,
    start_url: '',  // NO auto-navigation! Agent decides where to go based on user instruction
    step_offset: stepOffset  // Send offset to backend for proper numbering
  }))
  
  // Browser will be opened
  hasBrowser.value = true
}

async function handleSaveWorkflow(workflowData) {
  if (!currentTaskId.value) {
    showToast('No task to save', 'error')
    return
  }

  try {
    const response = await fetch('http://localhost:8000/workflows/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        task_id: currentTaskId.value,
        name: workflowData.name,
        description: workflowData.description,
        tags: [workflowData.category],
        steps: steps.value  // Send ALL accumulated steps, not just last task's steps
      })
    })

    if (response.ok) {
      showToast(`Workflow "${workflowData.name}" saved with ${steps.value.length} steps!`, 'success')
      addMessage('system', `Saved workflow: ${workflowData.name} (${steps.value.length} steps)`)
    } else {
      const error = await response.json()
      showToast(`Error: ${error.detail}`, 'error')
    }
  } catch (err) {
    showToast(`Error saving workflow: ${err.message}`, 'error')
  }
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
  // End session: close browser AND clear all accumulated data INCLUDING SESSION MEMORY
  if (websocket) {
    // Send the end_session message which clears session context on backend
    websocket.send(JSON.stringify({ type: 'end_session' }))
  }
  
  // Clear all local state
  steps.value = []
  allScreenshots.value = []
  currentScreenshot.value = null
  hasBrowser.value = false
  currentTaskId.value = null
  taskStatus.value = 'idle'
  
  showToast('Session ended - all data and memory cleared', 'info')
  addMessage('system', 'Test session ended. Browser closed and agent memory cleared.')
}



// Lifecycle
onMounted(() => {
  connectWebSocket()
})

onUnmounted(() => {
  if (websocket) {
    websocket.close()
  }
})
</script>

<style>
/* Toast Notifications */
.toast {
  position: fixed;
  bottom: 24px;
  right: 24px;
  padding: 14px 24px;
  background: var(--bg-secondary);
  color: var(--text-primary);
  border-radius: var(--radius-md);
  font-size: 0.9rem;
  font-weight: 500;
  box-shadow: var(--shadow-lg);
  z-index: 2000;
  animation: slideUp 0.35s cubic-bezier(0.16, 1, 0.3, 1);
  border: 1px solid var(--border-color);
}

.toast.success {
  background: var(--success);
  color: white;
  border-color: var(--success);
}

.toast.error {
  background: var(--error);
  color: white;
  border-color: var(--error);
}

.toast.info {
  background: var(--accent-primary);
  color: white;
  border-color: var(--accent-primary);
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(16px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}


</style>
