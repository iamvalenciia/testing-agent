/**
 * Test Plan Store
 * Manages semantic QA test plan execution state.
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useUiStore } from './ui'

const WS_URL = 'ws://localhost:8000/ws/test-plan'

export const useTestPlanStore = defineStore('testPlan', () => {
    const uiStore = useUiStore()

    // Connection
    const isConnected = ref(false)
    let websocket = null

    // Test Plan State
    const testPlan = ref(null)
    const executionStatus = ref('idle') // 'idle' | 'running' | 'completed' | 'error' | 'stopped'
    const currentStepId = ref(null)
    const progress = ref(0)

    // Steps State
    const stepsStatus = ref({}) // { stepId: 'pending' | 'running' | 'pass' | 'fail' | 'skipped' }
    const stepsResults = ref([])
    const screenshots = ref({}) // { stepId: base64 }

    // Execution Result
    const executionResult = ref(null)

    // Logs
    const executionLogs = ref([])

    // Computed
    const isRunning = computed(() => executionStatus.value === 'running')

    const totalSteps = computed(() => testPlan.value?.steps?.length || 0)

    const passedSteps = computed(() =>
        Object.values(stepsStatus.value).filter(s => s === 'pass').length
    )

    const failedSteps = computed(() =>
        Object.values(stepsStatus.value).filter(s => s === 'fail').length
    )

    const hasFailedSteps = computed(() => failedSteps.value > 0)

    // WebSocket Management
    function connect() {
        if (websocket?.readyState === WebSocket.OPEN) return

        websocket = new WebSocket(WS_URL)

        websocket.onopen = () => {
            isConnected.value = true
            addLog('info', 'Connected to test execution server')
            console.log('[TestPlan WS] Connected')
        }

        websocket.onclose = () => {
            isConnected.value = false
            console.log('[TestPlan WS] Disconnected')
            // Reconnect after 3 seconds
            setTimeout(() => {
                if (!isConnected.value) connect()
            }, 3000)
        }

        websocket.onerror = (err) => {
            console.error('[TestPlan WS] Error:', err)
            addLog('error', 'WebSocket connection error')
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
        switch (data.type) {
            case 'step_status':
                // Update step status
                stepsStatus.value[data.step_id] = data.status
                currentStepId.value = data.step_id
                addLog(
                    data.status === 'fail' ? 'error' : 'info',
                    `Step ${data.step_id}: ${data.message || data.status}`
                )
                break

            case 'execution_status':
                // Overall execution status update
                progress.value = data.progress
                if (data.steps_status) {
                    stepsStatus.value = { ...stepsStatus.value, ...data.steps_status }
                }
                if (data.message) {
                    addLog('info', data.message)
                }
                break

            case 'step_result':
                // Complete step result
                stepsResults.value.push(data.result)
                stepsStatus.value[data.step_id] = data.status
                break

            case 'screenshot':
                // Screenshot for current step
                if (currentStepId.value) {
                    screenshots.value[currentStepId.value] = data.data
                }
                break

            case 'completed':
                // Execution completed
                executionStatus.value = 'completed'
                executionResult.value = data.result
                addLog('success', `Execution completed: ${data.result?.overall_status?.toUpperCase()}`)
                uiStore.showToast(
                    `Test ${data.result?.overall_status === 'pass' ? 'passed' : 'completed with failures'}`,
                    data.result?.overall_status === 'pass' ? 'success' : 'warning'
                )
                break

            case 'status':
                if (data.status === 'stopped') {
                    executionStatus.value = 'stopped'
                    addLog('warning', 'Execution stopped')
                }
                break

            case 'error':
                executionStatus.value = 'error'
                addLog('error', data.message)
                uiStore.showToast(data.message, 'error')
                break

            case 'pong':
                // Heartbeat response
                break
        }
    }

    // Actions
    function setTestPlan(plan) {
        testPlan.value = plan
        // Initialize steps status
        stepsStatus.value = {}
        if (plan?.steps) {
            plan.steps.forEach(step => {
                stepsStatus.value[step.step_id] = 'pending'
            })
        }
        stepsResults.value = []
        screenshots.value = {}
        executionResult.value = null
        progress.value = 0
    }

    function executeTestPlan(options = {}) {
        if (!testPlan.value || isRunning.value) return

        // Reset state
        executionStatus.value = 'running'
        currentStepId.value = null
        stepsResults.value = []
        screenshots.value = {}
        executionResult.value = null
        progress.value = 0

        // Reset step statuses
        if (testPlan.value?.steps) {
            testPlan.value.steps.forEach(step => {
                stepsStatus.value[step.step_id] = 'pending'
            })
        }

        addLog('info', `Starting execution: ${testPlan.value.test_case_id}`)

        if (websocket?.readyState === WebSocket.OPEN) {
            websocket.send(JSON.stringify({
                type: 'execute',
                test_plan: testPlan.value,
                options: {
                    start_from_step: options.startFromStep || 1,
                    stop_on_failure: options.stopOnFailure ?? true,
                    max_retries_per_step: options.maxRetries ?? 3
                }
            }))
        } else {
            uiStore.showToast('Not connected to server', 'error')
            executionStatus.value = 'idle'
        }
    }

    function executeStep(step) {
        if (isRunning.value) return

        addLog('info', `Executing single step: ${step.step_id}`)

        if (websocket?.readyState === WebSocket.OPEN) {
            executionStatus.value = 'running'
            currentStepId.value = step.step_id
            stepsStatus.value[step.step_id] = 'running'

            websocket.send(JSON.stringify({
                type: 'execute_step',
                step: step
            }))
        } else {
            uiStore.showToast('Not connected to server', 'error')
        }
    }

    function resumeFromFailure() {
        if (!testPlan.value || isRunning.value) return

        // Find first failed step
        const failedStepId = Object.entries(stepsStatus.value)
            .find(([id, status]) => status === 'fail')?.[0]

        if (failedStepId) {
            addLog('info', `Resuming from step ${failedStepId}`)

            if (websocket?.readyState === WebSocket.OPEN) {
                executionStatus.value = 'running'

                websocket.send(JSON.stringify({
                    type: 'resume',
                    test_plan: testPlan.value,
                    from_step: parseInt(failedStepId)
                }))
            }
        }
    }

    function stopExecution() {
        if (websocket?.readyState === WebSocket.OPEN) {
            websocket.send(JSON.stringify({ type: 'stop' }))
        }
        executionStatus.value = 'stopped'
        addLog('warning', 'Stop requested')
    }

    function closeBrowser() {
        if (websocket?.readyState === WebSocket.OPEN) {
            websocket.send(JSON.stringify({ type: 'close_browser' }))
        }
    }

    function reset() {
        testPlan.value = null
        executionStatus.value = 'idle'
        currentStepId.value = null
        progress.value = 0
        stepsStatus.value = {}
        stepsResults.value = []
        screenshots.value = {}
        executionResult.value = null
        executionLogs.value = []
    }

    function addLog(type, message) {
        executionLogs.value.push({
            id: Date.now(),
            type,
            time: new Date().toLocaleTimeString(),
            message
        })

        // Keep only last 100 logs
        if (executionLogs.value.length > 100) {
            executionLogs.value = executionLogs.value.slice(-100)
        }
    }

    function clearLogs() {
        executionLogs.value = []
    }

    return {
        // State
        isConnected,
        testPlan,
        executionStatus,
        currentStepId,
        progress,
        stepsStatus,
        stepsResults,
        screenshots,
        executionResult,
        executionLogs,

        // Computed
        isRunning,
        totalSteps,
        passedSteps,
        failedSteps,
        hasFailedSteps,

        // Actions
        connect,
        disconnect,
        setTestPlan,
        executeTestPlan,
        executeStep,
        resumeFromFailure,
        stopExecution,
        closeBrowser,
        reset,
        addLog,
        clearLogs,
    }
})
