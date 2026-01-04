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

        <!-- Static Data - ALWAYS VISIBLE -->
        <button 
          class="control-btn static" 
          @click="openStaticDataModal"
          title="Save Static Reference Data"
          :disabled="isSavingStaticData"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>
          STATIC DATA
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

      <!-- Center: Viewport (Live View) + Steps -->
      <section class="viewport-panel">
        <div style="flex: 1; min-height: 0; position: relative;">
          <LiveView 
            :screenshot="currentScreenshot" 
            :status="taskStatus"
            :is-dark="isDark"
          />
        </div>
        <!-- Moved Steps to Bottom -->
        <div style="height: 160px; min-height: 160px;">
          <StepLog :steps="steps" :is-dark="isDark" @view-image="handleViewImage" />
        </div>
      </section>

      <!-- Right Panel Removed -->

    </main>

    <!-- Save Workflow Modal -->
    <div 
      v-if="showSaveModal && saveModalType === 'workflow'" 
      class="modal-overlay" 
      :class="{ 'saving-locked': isSaving }"
      @click.self="handleModalOverlayClick"
    >
      <div class="modal-content glass-panel" :class="{ 'is-saving': isSaving }">
        <!-- Progress Bar (visible during save) -->
        <div v-if="isSaving" class="save-progress-container">
          <div class="save-progress-bar">
            <div class="save-progress-fill"></div>
          </div>
          <span class="save-progress-text">Saving workflow to Pinecone...</span>
        </div>
        
        <h3>SAVE WORKFLOW TO PINECONE</h3>
        <div class="form-row">
          <div class="form-group half">
            <label>NAMESPACE</label>
            <select v-model="workflowForm.namespace" :disabled="isSaving">
              <option value="test_execution_steps">Test Execution Steps</option>
              <option value="test_success_cases">Test Success Cases</option>
            </select>
          </div>
          <div class="form-group half">
            <label>INDEX</label>
            <select v-model="workflowForm.index" :disabled="isSaving">
              <option value="steps-index">steps-index</option>
              <option value="hammer-index">hammer-index</option>
            </select>
          </div>
        </div>
        <div class="form-group">
          <label>GOALS TEXT (auto-filled from user prompts)</label>
          <textarea 
            v-model="workflowForm.text" 
            rows="3" 
            readonly 
            class="readonly-field"
            :disabled="isSaving"
          ></textarea>
        </div>
        <div class="modal-actions">
          <button 
            class="btn secondary" 
            @click="closeSaveModal" 
            :disabled="isSaving"
            :class="{ 'btn-disabled': isSaving }"
          >
            {{ isSaving ? 'PLEASE WAIT...' : 'CANCEL' }}
          </button>
          <button 
            class="btn primary" 
            @click="submitWorkflow" 
            :disabled="isSaving"
            :class="{ 'btn-saving': isSaving }"
          >
            <span v-if="isSaving" class="saving-spinner"></span>
            {{ isSaving ? 'SAVING...' : 'SAVE' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Save Success Case Modal -->
    <div 
      v-if="showSaveModal && saveModalType === 'success'" 
      class="modal-overlay" 
      :class="{ 'saving-locked': isSavingSuccess }"
      @click.self="handleSuccessModalOverlayClick"
    >
      <div class="modal-content glass-panel" :class="{ 'is-saving': isSavingSuccess }">
        <!-- Progress Bar (visible during save) -->
        <div v-if="isSavingSuccess" class="save-progress-container">
          <div class="save-progress-bar">
            <div class="save-progress-fill"></div>
          </div>
          <span class="save-progress-text">Saving success case...</span>
        </div>
        
        <h3>SAVE SUCCESS CASE</h3>
        <div class="form-group">
          <label>GOAL TEXT</label>
          <input 
            v-model="successForm.goal_text" 
            type="text" 
            placeholder="What was the user's goal?" 
            :disabled="isSavingSuccess"
          />
        </div>
        <div class="form-group">
          <label>WORKFLOW NAME</label>
          <input 
            v-model="successForm.workflow_name" 
            type="text" 
            placeholder="Name for this successful pattern" 
            :disabled="isSavingSuccess"
          />
        </div>
        <div class="form-group">
          <label>COMPANY CONTEXT (optional)</label>
          <input 
            v-model="successForm.company_context" 
            type="text" 
            placeholder="e.g. Graphi Connect, Client Portal" 
            :disabled="isSavingSuccess"
          />
        </div>
        <div class="modal-actions">
          <button 
            class="btn secondary" 
            @click="closeSuccessModal" 
            :disabled="isSavingSuccess"
            :class="{ 'btn-disabled': isSavingSuccess }"
          >
            {{ isSavingSuccess ? 'PLEASE WAIT...' : 'CANCEL' }}
          </button>
          <button 
            class="btn primary" 
            @click="submitSuccessCase" 
            :disabled="isSavingSuccess"
            :class="{ 'btn-saving': isSavingSuccess }"
          >
            <span v-if="isSavingSuccess" class="saving-spinner"></span>
            {{ isSavingSuccess ? 'SAVING...' : 'SAVE' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Static Data Modal - ALWAYS AVAILABLE -->
    <div 
      v-if="showStaticDataModal" 
      class="modal-overlay" 
      :class="{ 'saving-locked': isSavingStaticData }"
      @click.self="handleStaticDataModalOverlayClick"
    >
      <div class="modal-content glass-panel static-data-modal" :class="{ 'is-saving': isSavingStaticData }">
        <!-- Progress Bar (visible during save) -->
        <div v-if="isSavingStaticData" class="save-progress-container">
          <div class="save-progress-bar">
            <div class="save-progress-fill"></div>
          </div>
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
          <button 
            class="btn secondary" 
            @click="closeStaticDataModal" 
            :disabled="isSavingStaticData"
            :class="{ 'btn-disabled': isSavingStaticData }"
          >
            {{ isSavingStaticData ? 'PLEASE WAIT...' : 'CANCEL' }}
          </button>
          <button 
            class="btn primary static-save" 
            @click="submitStaticData" 
            :disabled="isSavingStaticData || !staticDataForm.data.trim()"
            :class="{ 'btn-saving': isSavingStaticData }"
          >
            <span v-if="isSavingStaticData" class="saving-spinner"></span>
            {{ isSavingStaticData ? 'SAVING...' : 'SAVE' }}
          </button>
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
          
          <!-- Session Metrics (Real-time from WebSocket) -->
          <div class="report-section metrics-section" v-if="sessionMetrics">
            <h4>SESSION METRICS <span class="section-count live-indicator">● LIVE</span></h4>
            <div class="metrics-grid">
              <!-- Elapsed Time -->
              <div class="metric-card">
                <div class="metric-icon">⏱️</div>
                <div class="metric-data">
                  <span class="metric-value">{{ formatDuration(sessionMetrics.elapsed_seconds) }}</span>
                  <span class="metric-label">Session Duration</span>
                </div>
              </div>
              
              <!-- Agent Performance -->
              <div class="metric-card">
                <div class="metric-icon">🤖</div>
                <div class="metric-data">
                  <span class="metric-value">{{ sessionMetrics.agent?.turns || 0 }}</span>
                  <span class="metric-label">Agent Turns</span>
                  <span class="metric-sublabel" v-if="sessionMetrics.agent?.avg_turn_duration_seconds">
                    ~{{ sessionMetrics.agent.avg_turn_duration_seconds }}s avg
                  </span>
                </div>
              </div>
              
              <!-- Tasks -->
              <div class="metric-card">
                <div class="metric-icon">✓</div>
                <div class="metric-data">
                  <span class="metric-value">{{ sessionMetrics.agent?.tasks_completed || 0 }}/{{ sessionMetrics.agent?.tasks_started || 0 }}</span>
                  <span class="metric-label">Tasks Completed</span>
                  <span class="metric-sublabel error" v-if="sessionMetrics.agent?.tasks_failed > 0">
                    {{ sessionMetrics.agent.tasks_failed }} failed
                  </span>
                </div>
              </div>
              
              <!-- Gemini API -->
              <div class="metric-card">
                <div class="metric-icon">🧠</div>
                <div class="metric-data">
                  <span class="metric-value">{{ sessionMetrics.gemini_api?.calls || 0 }}</span>
                  <span class="metric-label">Gemini API Calls</span>
                  <span class="metric-sublabel" v-if="sessionMetrics.gemini_api?.total_duration_seconds">
                    {{ sessionMetrics.gemini_api.total_duration_seconds }}s total
                  </span>
                </div>
              </div>
              
              <!-- Browser Actions -->
              <div class="metric-card">
                <div class="metric-icon">🌐</div>
                <div class="metric-data">
                  <span class="metric-value">{{ sessionMetrics.browser?.actions || 0 }}</span>
                  <span class="metric-label">Browser Actions</span>
                </div>
              </div>
              
              <!-- WebSocket Messages -->
              <div class="metric-card">
                <div class="metric-icon">📡</div>
                <div class="metric-data">
                  <span class="metric-value">{{ (sessionMetrics.websocket_messages?.sent || 0) + (sessionMetrics.websocket_messages?.received || 0) }}</span>
                  <span class="metric-label">WS Messages</span>
                  <span class="metric-sublabel">
                    ↑{{ sessionMetrics.websocket_messages?.sent || 0 }} ↓{{ sessionMetrics.websocket_messages?.received || 0 }}
                  </span>
                </div>
              </div>
            </div>
          </div>
          <div class="report-section metrics-section" v-else>
            <h4>SESSION METRICS</h4>
            <p class="metrics-empty">No metrics available yet. Start a task to see real-time metrics.</p>
          </div>
          
          <!-- Guardrail Analysis Section -->
          <div class="report-section guardrails-section" v-if="sessionMetrics?.guardrails">
            <h4>GUARDRAIL ANALYSIS <span class="section-count" :class="guardrailStatusClass">{{ guardrailStatusIcon }}</span></h4>
            <div class="guardrails-grid">
              <!-- Step Count Comparison -->
              <div class="guardrail-card" :class="{ warning: sessionMetrics.guardrails.extra_steps?.length > 0 }">
                <div class="guardrail-icon">📊</div>
                <div class="guardrail-data">
                  <span class="guardrail-title">Step Count</span>
                  <div class="step-comparison">
                    <span class="expected" v-if="sessionMetrics.guardrails.step_count_expected">
                      Expected: <strong>{{ sessionMetrics.guardrails.step_count_expected }}</strong>
                    </span>
                    <span class="actual">
                      Actual: <strong>{{ sessionMetrics.guardrails.step_count_actual || steps.length }}</strong>
                    </span>
                  </div>
                  <div class="step-diff" v-if="sessionMetrics.guardrails.step_count_expected">
                    <span v-if="stepDifference > 0" class="diff-positive">+{{ stepDifference }} extra steps</span>
                    <span v-else-if="stepDifference < 0" class="diff-negative">{{ stepDifference }} fewer steps</span>
                    <span v-else class="diff-exact">✓ Exact match</span>
                  </div>
                  <div v-else class="no-reference">No reference workflow</div>
                </div>
              </div>
              
              <!-- Extra Steps Detail -->
              <div class="guardrail-card" v-if="sessionMetrics.guardrails.extra_steps?.length > 0" :class="{ recovery: sessionMetrics.guardrails.adaptive_recovery }">
                <div class="guardrail-icon">{{ sessionMetrics.guardrails.adaptive_recovery ? '🔄' : '⚠️' }}</div>
                <div class="guardrail-data">
                  <span class="guardrail-title">Extra Actions</span>
                  <div class="extra-steps-list">
                    <span v-for="(action, i) in sessionMetrics.guardrails.extra_steps" :key="i" class="extra-step-tag">
                      {{ action }}
                    </span>
                  </div>
                  <div class="recovery-note" v-if="sessionMetrics.guardrails.adaptive_recovery">
                    ↳ Intelligent recovery (outcome correct)
                  </div>
                  <div class="drift-warning" v-else-if="sessionMetrics.guardrails.drift_detected">
                    ⚠️ DRIFT DETECTED
                  </div>
                </div>
              </div>
              
              <!-- Static Data Loading -->
              <div class="guardrail-card" :class="{ pollution: sessionMetrics.guardrails.context_pollution }">
                <div class="guardrail-icon">{{ sessionMetrics.guardrails.static_data_loaded ? '📚' : '📭' }}</div>
                <div class="guardrail-data">
                  <span class="guardrail-title">Static Data</span>
                  <span class="guardrail-value">{{ sessionMetrics.guardrails.static_data_loaded ? 'Loaded' : 'Not Loaded' }}</span>
                  <div class="pollution-warning" v-if="sessionMetrics.guardrails.context_pollution">
                    ⚠️ Context pollution - loaded but unused
                  </div>
                  <div class="used-note" v-else-if="sessionMetrics.guardrails.static_data_loaded">
                    ✓ Used in reasoning
                  </div>
                </div>
              </div>
              
              <!-- Overall Status -->
              <div class="guardrail-card status-card" :class="overallGuardrailStatus">
                <div class="guardrail-icon">{{ overallGuardrailIcon }}</div>
                <div class="guardrail-data">
                  <span class="guardrail-title">Overall Status</span>
                  <span class="guardrail-status">{{ overallGuardrailMessage }}</span>
                </div>
              </div>
            </div>
          </div>
          <div class="report-section guardrails-section" v-else>
            <h4>GUARDRAIL ANALYSIS</h4>
            <p class="guardrails-empty">Guardrail data will appear here after task completion.</p>
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
    <div v-if="zoomedImage" class="modal-overlay image-viewer" :class="{ 'dark-mode': isDark }" @click="zoomedImage = null">
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
const workflowForm = ref({ 
  name: '', 
  description: '', 
  namespace: 'test_execution_steps',
  index: 'steps-index',
  text: '' 
})
const successForm = ref({ goal_text: '', workflow_name: '', company_context: '' })

// Loading state for save button (prevents multiple clicks)
const isSaving = ref(false)
const isSavingSuccess = ref(false)

// Static Data Modal State
const showStaticDataModal = ref(false)
const staticDataForm = ref({ data: '' })
const isSavingStaticData = ref(false)
const MAX_STATIC_DATA_CHARS = 10000

// Report Modal State
const showReportModal = ref(false)
const sessionDate = ref(new Date().toLocaleString())

// Session Metrics - Real-time from WebSocket
const sessionMetrics = ref(null)

let websocket = null

// Computed
const isRunning = computed(() => taskStatus.value === 'running' || taskStatus.value === 'starting')

const connectionStatusClass = computed(() => ({
  'connected': isConnected.value && !isRunning.value,
  'running': isRunning.value,
  'disconnected': !isConnected.value
}))

// Guardrail Computed Properties
const stepDifference = computed(() => {
  if (!sessionMetrics.value?.guardrails?.step_count_expected) return 0
  const actual = sessionMetrics.value.guardrails.step_count_actual || steps.value.length
  return actual - sessionMetrics.value.guardrails.step_count_expected
})

const guardrailStatusClass = computed(() => {
  const gr = sessionMetrics.value?.guardrails
  if (!gr) return ''
  if (gr.drift_detected) return 'drift-detected'
  if (gr.adaptive_recovery) return 'recovery-mode'
  if (gr.context_pollution) return 'pollution-warning'
  return 'all-passed'
})

const guardrailStatusIcon = computed(() => {
  const gr = sessionMetrics.value?.guardrails
  if (!gr) return '⏳'
  if (gr.drift_detected) return '⚠️ DRIFT'
  if (gr.adaptive_recovery) return '🔄 RECOVERY'
  if (gr.context_pollution) return '📛 POLLUTION'
  return '✓ PASS'
})

const overallGuardrailStatus = computed(() => {
  const gr = sessionMetrics.value?.guardrails
  if (!gr) return 'pending'
  if (gr.drift_detected) return 'drift'
  if (gr.adaptive_recovery) return 'recovery'
  if (gr.context_pollution) return 'pollution'
  return 'passed'
})

const overallGuardrailIcon = computed(() => {
  const status = overallGuardrailStatus.value
  return {
    'pending': '⏳',
    'drift': '⚠️',
    'recovery': '🔄',
    'pollution': '📛',
    'passed': '✓'
  }[status] || '✓'
})

const overallGuardrailMessage = computed(() => {
  const gr = sessionMetrics.value?.guardrails
  if (!gr) return 'Awaiting task completion...'
  if (gr.drift_detected) return 'Drift detected - agent deviated from expected behavior'
  if (gr.adaptive_recovery) return 'Task completed with intelligent recovery'
  if (gr.context_pollution) return 'Context pollution - unnecessary data loaded'
  return 'All checks passed'
})

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

// Format seconds to human-readable duration (e.g., "2m 35s")
function formatDuration(seconds) {
  if (!seconds || seconds < 0) return '0s'
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  if (mins > 0) {
    return `${mins}m ${secs}s`
  }
  return `${secs}s`
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

    case 'metrics':
      // Real-time session metrics from backend
      sessionMetrics.value = data.data
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
    // Auto-fill text with all user goals/prompts
    const allUserGoals = messages.value
      .filter(m => m.role === 'user')
      .map(m => m.content)
      .join('\n')
    
    workflowForm.value = { 
      name: '', 
      description: '',
      namespace: 'test_execution_steps',
      index: 'steps-index',
      text: allUserGoals
    }
  } else {
    // Pre-fill with last goal
    successForm.value = { 
      goal_text: lastGoal.value, 
      workflow_name: '', 
      company_context: '' 
    }
  }
}

// Handler for modal overlay click - blocks closing while saving
function handleModalOverlayClick() {
  if (isSaving.value) {
    showToast('Please wait, save operation in progress...', 'info')
    return
  }
  closeSaveModal()
}

function closeSaveModal() {
  // Extra safety: prevent closing while saving
  if (isSaving.value) {
    showToast('Cannot close modal while saving', 'info')
    return
  }
  showSaveModal.value = false
}

// Handler for success case modal overlay click
function handleSuccessModalOverlayClick() {
  if (isSavingSuccess.value) {
    showToast('Please wait, save operation in progress...', 'info')
    return
  }
  closeSuccessModal()
}

function closeSuccessModal() {
  if (isSavingSuccess.value) {
    showToast('Cannot close modal while saving', 'info')
    return
  }
  showSaveModal.value = false
}

// Save Workflow
async function submitWorkflow() {
  if (!currentTaskId.value) {
    showToast('No active task to save', 'error')
    return
  }

  // Prevent multiple clicks
  if (isSaving.value) return
  isSaving.value = true

  try {
    // Extract URLs visited (unique)
    const urlsVisited = [...new Set(steps.value.map(s => s.url).filter(Boolean))]
    
    // Count actions performed by type
    const actionsPerformed = steps.value.reduce((acc, step) => {
      const action = step.action_type || step.action || 'unknown'
      acc[action] = (acc[action] || 0) + 1
      return acc
    }, {})
    
    // Build steps reference (without x,y coordinates)
    const stepsReferenceOnly = steps.value.map((s, i) => ({
      step: i + 1,
      timestamp: s.timestamp,
      url: s.url || null,
      reasoning: s.reasoning || null
    }))
    
    // Extract User Prompts
    const userPrompts = messages.value
      .filter(m => m.role === 'user')
      .map(m => m.content)

    const response = await fetch('http://localhost:8000/workflows/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        task_id: currentTaskId.value,
        name: 'workflow',  // Default name for ID generation
        description: '',
        namespace: workflowForm.value.namespace,
        index: workflowForm.value.index,
        text: workflowForm.value.text,
        urls_visited: urlsVisited,
        actions_performed: actionsPerformed,
        steps_reference_only: stepsReferenceOnly,
        user_prompts: userPrompts, // Added user prompts
        tags: ['workflow'],
        steps: steps.value.map(s => {
          const { screenshot, ...rest } = s
          return rest
        })
      })
    })

    if (response.ok) {
      showToast('Workflow saved to Pinecone ✓', 'success')
      // Reset saving state BEFORE closing modal so it can actually close
      isSaving.value = false
      showSaveModal.value = false  // Directly close the modal
    } else {
      const err = await response.json()
      showToast(err.detail || 'Save failed', 'error')
    }
  } catch (e) {
    showToast('Error: ' + e.message, 'error')
  } finally {
    isSaving.value = false
  }
}

// Save Success Case
async function submitSuccessCase() {
  if (!successForm.value.goal_text || !successForm.value.workflow_name) {
    showToast('Please fill goal and workflow name', 'error')
    return
  }

  // Prevent multiple clicks
  if (isSavingSuccess.value) return
  isSavingSuccess.value = true

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
      isSavingSuccess.value = false // Reset before closing
      closeSuccessModal()
    } else {
      const err = await response.json()
      showToast(err.detail || 'Save failed', 'error')
    }
  } catch (e) {
    showToast('Error: ' + e.message, 'error')
  } finally {
    isSavingSuccess.value = false
  }
}

// Static Data Modal Functions
function openStaticDataModal() {
  staticDataForm.value = { data: '' }
  showStaticDataModal.value = true
}

function handleStaticDataModalOverlayClick() {
  if (isSavingStaticData.value) {
    showToast('Please wait, save operation in progress...', 'info')
    return
  }
  closeStaticDataModal()
}

function closeStaticDataModal() {
  if (isSavingStaticData.value) {
    showToast('Cannot close modal while saving', 'info')
    return
  }
  showStaticDataModal.value = false
}

async function submitStaticData() {
  if (!staticDataForm.value.data.trim()) {
    showToast('Data field cannot be empty', 'error')
    return
  }

  // Prevent multiple clicks
  if (isSavingStaticData.value) return
  isSavingStaticData.value = true

  try {
    const response = await fetch('http://localhost:8000/static-data', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        data: staticDataForm.value.data
      })
    })

    if (response.ok) {
      const result = await response.json()
      showToast(`Static data saved ✓ (${result.char_count} chars)`, 'success')
      isSavingStaticData.value = false
      showStaticDataModal.value = false
    } else {
      const err = await response.json()
      showToast(err.detail || 'Save failed', 'error')
    }
  } catch (e) {
    showToast('Error: ' + e.message, 'error')
  } finally {
    isSavingStaticData.value = false
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
  
  // Session Metrics (Real-time from WebSocket)
  if (sessionMetrics.value) {
    report += 'SESSION METRICS\n'
    report += '-'.repeat(30) + '\n'
    report += `Session Duration: ${formatDuration(sessionMetrics.value.elapsed_seconds)}\n`
    report += `Agent Turns: ${sessionMetrics.value.agent?.turns || 0}`
    if (sessionMetrics.value.agent?.avg_turn_duration_seconds) {
      report += ` (~${sessionMetrics.value.agent.avg_turn_duration_seconds}s avg)`
    }
    report += '\n'
    report += `Tasks: ${sessionMetrics.value.agent?.tasks_completed || 0}/${sessionMetrics.value.agent?.tasks_started || 0} completed`
    if (sessionMetrics.value.agent?.tasks_failed > 0) {
      report += ` (${sessionMetrics.value.agent.tasks_failed} failed)`
    }
    report += '\n'
    report += `Gemini API Calls: ${sessionMetrics.value.gemini_api?.calls || 0}`
    if (sessionMetrics.value.gemini_api?.total_duration_seconds) {
      report += ` (${sessionMetrics.value.gemini_api.total_duration_seconds}s total)`
    }
    report += '\n'
    report += `Browser Actions: ${sessionMetrics.value.browser?.actions || 0}\n`
    const totalWs = (sessionMetrics.value.websocket_messages?.sent || 0) + (sessionMetrics.value.websocket_messages?.received || 0)
    report += `WebSocket Messages: ${totalWs} (↑${sessionMetrics.value.websocket_messages?.sent || 0} ↓${sessionMetrics.value.websocket_messages?.received || 0})\n\n`
    
    // GUARDRAIL ANALYSIS (from backend validators)
    if (sessionMetrics.value.guardrails) {
      const gr = sessionMetrics.value.guardrails
      report += 'GUARDRAIL ANALYSIS\n'
      report += '-'.repeat(30) + '\n'
      
      // Step count comparison with more detail
      if (gr.step_count_expected !== undefined && gr.step_count_expected !== null) {
        report += `Reference Workflow Steps: ${gr.step_count_expected}\n`
        report += `Agent Actual Steps: ${gr.step_count_actual || steps.value.length}\n`
        
        const diff = (gr.step_count_actual || steps.value.length) - gr.step_count_expected
        report += `Step Difference: ${diff >= 0 ? '+' : ''}${diff}\n`
        
        if (diff > 1) {
          if (gr.extra_steps && gr.extra_steps.length > 0) {
            report += `\nExtra Actions Detected:\n`
            gr.extra_steps.forEach((action, i) => {
              report += `  ${i + 1}. ${action}\n`
            })
          }
          if (gr.adaptive_recovery) {
            report += `\n[RECOVERY] These extra steps were flagged as INTELLIGENT RECOVERY:\n`
            report += `  - The agent adapted when primary action didn't work\n`
            report += `  - Final outcome matches expected result\n`
            report += `  - Consider: This may indicate the reference workflow is outdated\n`
          } else if (gr.drift_detected) {
            report += `\n[DRIFT] ⚠️ AGENT DRIFT DETECTED:\n`
            report += `  - Agent performed more steps than reference workflow\n`
            report += `  - Outcome may not match expected result\n`
            report += `  - ACTION: Review reference workflow and agent behavior\n`
          }
        } else if (diff < -1) {
          report += `\n[EFFICIENT] Agent completed in fewer steps:\n`
          report += `  - ${Math.abs(diff)} steps saved vs reference\n`
          report += `  - This may indicate improved agent efficiency\n`
        } else {
          report += `\n[OK] Step count within acceptable tolerance (±1)\n`
        }
      } else {
        report += `Total Steps: ${steps.value.length}\n`
        report += `Reference: No workflow found for comparison\n`
        report += `  - Agent executed without prior workflow guidance\n`
        report += `  - Consider saving this workflow for future reference\n`
      }
      
      // Static data loading analysis
      report += `\nStatic Data Analysis:\n`
      report += `  Loaded: ${gr.static_data_loaded ? 'Yes' : 'No'}\n`
      if (gr.context_pollution) {
        report += `  [POLLUTION] ⚠️ CONTEXT POLLUTION DETECTED:\n`
        report += `    - Static data was loaded but NOT used in reasoning\n`
        report += `    - This wastes tokens and may confuse the agent\n`
        report += `    - ACTION: Review lazy loading keywords in agent.py\n`
      } else if (gr.static_data_loaded) {
        report += `  [OK] Static data was referenced in agent reasoning\n`
      } else {
        report += `  [OK] Static data correctly not loaded for this task\n`
      }
      
      // Validator details if available
      if (gr.validators) {
        report += `\nValidator Results:\n`
        Object.entries(gr.validators).forEach(([name, result]) => {
          const icon = result.valid ? '✓' : '⚠️'
          report += `  ${icon} ${name}: ${result.message}\n`
        })
      }
      
      // Overall summary
      report += `\n${'─'.repeat(30)}\n`
      if (gr.drift_detected) {
        report += `⚠️ OVERALL: DRIFT DETECTED\n`
        report += `   Recommended: Review this execution for issues\n`
      } else if (gr.adaptive_recovery) {
        report += `🔄 OVERALL: INTELLIGENT RECOVERY\n`
        report += `   Note: Agent adapted successfully, consider updating workflow\n`
      } else if (gr.context_pollution) {
        report += `📛 OVERALL: CONTEXT POLLUTION WARNING\n`
        report += `   Note: Task completed but used unnecessary context\n`
      } else {
        report += `✓ OVERALL: ALL GUARDRAIL CHECKS PASSED\n`
        report += `   Agent behavior matches expected patterns\n`
      }
      
      report += '\n'
    }
  }
  
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
    // Keep meaningful agent messages
    if (content.includes('complete') || content.includes('error') || 
        // Filter out "starting" and "Task... starting"
        (content.includes('subtask') && !content.includes('starting')) ||
        content.includes('decomposed') || content.includes('success') ||
        content.includes('failed') || content.includes('navigating') ||
        content.includes('loading') || content.includes('credentials') ||
        content.includes('submitting') || content.includes('changing') ||
        content.includes('safety') || (msg.content.length > 100 && !content.includes('starting'))) return true
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

/* Static Data Button - Always visible, unique color */
.control-btn.static {
  background: rgba(99, 102, 241, 0.1);
  border-color: rgba(99, 102, 241, 0.3);
  color: #818cf8;
}

.control-btn.static:hover {
  background: rgba(99, 102, 241, 0.2);
}

.control-btn.static:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Static Data Modal Styles */
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

/* Main Grid */
.main-grid {
  display: grid;
  grid-template-columns: 45% 1fr;
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
  display: flex;
  flex-direction: column;
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
.form-group textarea:focus,
.form-group select:focus {
  border-color: var(--text-primary);
}

.form-row {
  display: flex;
  gap: 1rem;
  margin-bottom: 0.75rem;
}

.form-group.half {
  flex: 1;
}

.form-group select {
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
  cursor: pointer;
}

.form-group select option {
  background: var(--bg-secondary);
  color: var(--text-primary);
}

.readonly-field {
  opacity: 0.7;
  cursor: not-allowed;
  background: var(--bg-secondary) !important;
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

/* Save Modal Security States */
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

/* Save Progress Bar */
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
  0% {
    transform: translateX(-100%);
    background-position: 0% 0%;
  }
  50% {
    background-position: 100% 0%;
  }
  100% {
    transform: translateX(400%);
    background-position: 0% 0%;
  }
}

.save-progress-text {
  font-size: 0.7rem;
  color: var(--text-muted);
  letter-spacing: 1px;
  text-transform: uppercase;
}

/* Saving Spinner */
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

/* Disabled Button States */
.btn.btn-disabled,
.btn.btn-saving {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn.btn-disabled:hover,
.btn.btn-saving:hover {
  opacity: 0.6;
}

.btn.btn-saving {
  display: flex;
  align-items: center;
  justify-content: center;
}

/* Form elements disabled state */
.form-group select:disabled,
.form-group input:disabled,
.form-group textarea:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  background: var(--bg-tertiary);
}

/* Image Viewer */
.image-viewer img {
  max-width: 90vw;
  max-height: 90vh;
  border-radius: 8px;
  box-shadow: 0 0 50px rgba(0, 0, 0, 0.5);
  transition: all 0.3s ease;
}

/* Dark Mode: Filter for full screen image */
.image-viewer.dark-mode img {
  filter: brightness(0.6) saturate(0.6);
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

/* ===== METRICS SECTION STYLES ===== */
.metrics-section h4 {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.live-indicator {
  color: #10b981;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 1rem;
  margin-top: 0.75rem;
}

.metric-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 1rem;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  transition: all 0.2s;
}

.metric-card:hover {
  border-color: var(--accent);
  transform: translateY(-2px);
}

.metric-icon {
  font-size: 1.5rem;
  filter: saturate(0.8);
}

.metric-data {
  display: flex;
  flex-direction: column;
}

.metric-value {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text-primary);
  font-family: 'JetBrains Mono', monospace;
}

.metric-label {
  font-size: 0.65rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.metric-sublabel {
  font-size: 0.6rem;
  color: var(--text-secondary);
  margin-top: 2px;
}

.metric-sublabel.error {
  color: #ef4444;
}

.metrics-empty {
  color: var(--text-muted);
  font-size: 0.8rem;
  font-style: italic;
  padding: 1rem 0;
}

/* Guardrails Section */
.guardrails-section h4 {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.guardrails-section .section-count {
  font-size: 0.7rem;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 600;
}

.guardrails-section .section-count.all-passed {
  background: rgba(16, 185, 129, 0.2);
  color: #10b981;
}

.guardrails-section .section-count.recovery-mode {
  background: rgba(99, 102, 241, 0.2);
  color: #818cf8;
}

.guardrails-section .section-count.drift-detected,
.guardrails-section .section-count.pollution-warning {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
}

.guardrails-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 0.75rem;
}

.guardrail-card {
  display: flex;
  gap: 0.75rem;
  padding: 0.75rem;
  background: var(--bg-tertiary);
  border-radius: 8px;
  border: 1px solid var(--border-color);
  transition: all 0.2s;
}

.guardrail-card.warning {
  border-color: rgba(245, 158, 11, 0.4);
  background: rgba(245, 158, 11, 0.05);
}

.guardrail-card.recovery {
  border-color: rgba(99, 102, 241, 0.4);
  background: rgba(99, 102, 241, 0.05);
}

.guardrail-card.pollution {
  border-color: rgba(239, 68, 68, 0.4);
  background: rgba(239, 68, 68, 0.05);
}

.guardrail-card.status-card.passed {
  border-color: rgba(16, 185, 129, 0.4);
  background: rgba(16, 185, 129, 0.05);
}

.guardrail-card.status-card.drift,
.guardrail-card.status-card.pollution {
  border-color: rgba(239, 68, 68, 0.4);
  background: rgba(239, 68, 68, 0.05);
}

.guardrail-card.status-card.recovery {
  border-color: rgba(99, 102, 241, 0.4);
  background: rgba(99, 102, 241, 0.05);
}

.guardrail-icon {
  font-size: 1.25rem;
  width: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.guardrail-data {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
}

.guardrail-title {
  font-size: 0.65rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 600;
}

.guardrail-value,
.guardrail-status {
  font-size: 0.85rem;
  color: var(--text-primary);
  font-weight: 500;
}

.step-comparison {
  display: flex;
  gap: 1rem;
  font-size: 0.8rem;
  color: var(--text-secondary);
}

.step-comparison strong {
  color: var(--text-primary);
  font-family: 'JetBrains Mono', monospace;
}

.step-diff {
  margin-top: 2px;
  font-size: 0.7rem;
}

.step-diff .diff-positive {
  color: #f59e0b;
}

.step-diff .diff-negative {
  color: #10b981;
}

.step-diff .diff-exact {
  color: #10b981;
}

.no-reference {
  font-size: 0.7rem;
  color: var(--text-muted);
  font-style: italic;
}

.extra-steps-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 2px;
}

.extra-step-tag {
  font-size: 0.65rem;
  padding: 2px 6px;
  background: rgba(245, 158, 11, 0.2);
  color: #f59e0b;
  border-radius: 4px;
  font-family: 'JetBrains Mono', monospace;
}

.recovery-note {
  font-size: 0.65rem;
  color: #818cf8;
  margin-top: 4px;
}

.drift-warning,
.pollution-warning {
  font-size: 0.65rem;
  color: #ef4444;
  margin-top: 4px;
  font-weight: 600;
}

.used-note {
  font-size: 0.65rem;
  color: #10b981;
  margin-top: 2px;
}

.guardrails-empty {
  color: var(--text-muted);
  font-size: 0.8rem;
  font-style: italic;
  padding: 1rem 0;
}
</style>
