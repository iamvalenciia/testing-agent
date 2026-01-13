/**
 * Session Store
 * Manages WebSocket connection, steps, messages, metrics, and task state.
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useAuthStore } from './auth'
import { useUiStore } from './ui'

const WS_URL = 'ws://localhost:8000/ws'

export const useSessionStore = defineStore('session', () => {
    const authStore = useAuthStore()
    const uiStore = useUiStore()

    // Connection
    const isConnected = ref(false)
    const hasBrowser = ref(false)
    let websocket = null

    // Task State
    const taskStatus = ref('idle') // 'idle' | 'starting' | 'running' | 'completed' | 'error'
    const currentTaskId = ref(null)
    const lastGoal = ref('')
    const isProductionMode = ref(false)

    // Data
    const messages = ref([])
    const steps = ref([])
    const allScreenshots = ref([])
    const currentScreenshot = ref(null)
    const sessionMetrics = ref(null)
    const sessionDate = ref(new Date().toLocaleString())

    // Computed
    const isRunning = computed(() => taskStatus.value === 'running' || taskStatus.value === 'starting')

    const connectionStatusClass = computed(() => ({
        'connected': isConnected.value && !isRunning.value,
        'running': isRunning.value,
        'disconnected': !isConnected.value
    }))

    // WebSocket Management
    function connect() {
        if (websocket?.readyState === WebSocket.OPEN) return

        const token = authStore.getToken()
        const url = token ? `${WS_URL}?token=${token}` : WS_URL

        websocket = new WebSocket(url)

        websocket.onopen = () => {
            isConnected.value = true
            console.log('[WS] Connected')
        }

        websocket.onclose = () => {
            isConnected.value = false
            console.log('[WS] Disconnected')
            // Reconnect after 3 seconds
            setTimeout(() => {
                if (!isConnected.value) connect()
            }, 3000)
        }

        websocket.onerror = (err) => {
            console.error('[WS] Error:', err)
        }

        websocket.onmessage = (event) => {
            handleMessage(JSON.parse(event.data))
        }
    }

    function disconnect() {
        if (websocket) {
            websocket.close()
            websocket = null
        }
    }

    function handleMessage(data) {
        if (data.task_id && !currentTaskId.value) {
            currentTaskId.value = data.task_id
        }

        switch (data.type) {
            case 'status':
                if (data.status === 'browser_ready') hasBrowser.value = true
                if (data.status === 'browser_closed') hasBrowser.value = false
                if (data.status === 'started') taskStatus.value = 'running'
                if (data.status === 'completed') taskStatus.value = 'idle'
                if (data.status === 'error') {
                    taskStatus.value = 'idle'
                    uiStore.showToast(data.message || 'An error occurred', 'error')
                }
                break

            case 'screenshot':
                currentScreenshot.value = data.data
                allScreenshots.value.push({
                    data: data.data,
                    timestamp: new Date().toLocaleTimeString()
                })
                break

            case 'step':
                steps.value.push({
                    ...data,
                    timestamp: new Date().toLocaleTimeString()
                })
                break

            case 'message':
                messages.value.push({
                    id: Date.now(),
                    role: data.role || 'agent',
                    content: data.content,
                    timestamp: new Date().toLocaleTimeString()
                })
                break

            case 'metrics':
                sessionMetrics.value = data.metrics
                break
        }
    }

    // Actions
    function sendMessage(content) {
        if (!content.trim() || isRunning.value) return

        messages.value.push({
            id: Date.now(),
            role: 'user',
            content,
            timestamp: new Date().toLocaleTimeString()
        })

        lastGoal.value = content
        taskStatus.value = 'starting'

        if (websocket?.readyState === WebSocket.OPEN) {
            websocket.send(JSON.stringify({
                type: 'task',
                goal: content,
                mode: isProductionMode.value ? 'production' : 'training'
            }))
        } else {
            uiStore.showToast('Not connected to server', 'error')
            taskStatus.value = 'idle'
        }
    }

    function stopTask() {
        if (websocket?.readyState === WebSocket.OPEN) {
            websocket.send(JSON.stringify({ type: 'stop' }))
        }
        taskStatus.value = 'idle'
    }

    function closeBrowser() {
        if (websocket?.readyState === WebSocket.OPEN) {
            websocket.send(JSON.stringify({ type: 'close_browser' }))
        }
    }

    function endSession() {
        messages.value = []
        steps.value = []
        allScreenshots.value = []
        currentScreenshot.value = null
        sessionMetrics.value = null
        currentTaskId.value = null
        taskStatus.value = 'idle'
        sessionDate.value = new Date().toLocaleString()
    }

    function toggleMode() {
        isProductionMode.value = !isProductionMode.value
    }

    return {
        // State
        isConnected,
        hasBrowser,
        taskStatus,
        currentTaskId,
        lastGoal,
        isProductionMode,
        messages,
        steps,
        allScreenshots,
        currentScreenshot,
        sessionMetrics,
        sessionDate,
        // Computed
        isRunning,
        connectionStatusClass,
        // Actions
        connect,
        disconnect,
        sendMessage,
        stopTask,
        closeBrowser,
        endSession,
        toggleMode,
    }
})
