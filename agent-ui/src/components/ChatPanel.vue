<template>
  <section class="chat-panel">
    <!-- Messages Area -->
    <div class="messages-area" ref="messagesContainer">
      <div 
        v-for="msg in messages" 
        :key="msg.id" 
        class="message"
        :class="msg.role"
      >
        <div class="message-header">
          <span class="role-label">{{ msg.role === 'user' ? 'YOU' : msg.role === 'agent' ? 'AGENT' : 'SYSTEM' }}</span>
          <span class="timestamp">{{ msg.timestamp }}</span>
        </div>
        <div class="message-content" v-html="renderMarkdown(msg.content)"></div>
      </div>
      
      <div v-if="messages.length === 0" class="empty-hint">
        <span class="blink">_</span> Enter a command to begin...
      </div>
    </div>
    
    <!-- Input Area -->
    <div class="input-area">
      <div class="input-wrapper" :class="{ 'disabled': status === 'running' }">
        <textarea
          v-model="inputText"
          class="chat-input"
          placeholder="Describe your testing task..."
          @keydown.enter.exact.prevent="handleSend"
          :disabled="status === 'running'"
          rows="1"
          ref="textareaRef"
        ></textarea>
        
        <button 
          class="send-btn" 
          @click="status === 'running' ? $emit('stop') : handleSend()"
          :class="{ 'stop': status === 'running' }"
        >
          <svg v-if="status !== 'running'" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
            <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
          </svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            <rect x="6" y="6" width="12" height="12" rx="2"/>
          </svg>
        </button>
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue';
import { marked } from 'marked';

const props = defineProps({
  messages: {
    type: Array,
    default: () => []
  },
  status: {
    type: String,
    default: 'idle'
  },
  isDark: {
    type: Boolean,
    default: true
  }
});

const emit = defineEmits(['send-message', 'stop']);

const inputText = ref('');
const messagesContainer = ref(null);
const textareaRef = ref(null);

function handleSend() {
  if (!inputText.value.trim() || props.status === 'running') return;
  emit('send-message', inputText.value);
  inputText.value = '';
  if (textareaRef.value) textareaRef.value.style.height = 'auto';
}

function renderMarkdown(content) {
  if (!content) return '';
  return marked(content);
}

// Auto-scroll
watch(() => props.messages.length, async () => {
  await nextTick();
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
  }
});

// Auto-resize textarea
watch(inputText, () => {
  nextTick(() => {
    if (textareaRef.value) {
      textareaRef.value.style.height = 'auto';
      textareaRef.value.style.height = Math.min(textareaRef.value.scrollHeight, 120) + 'px';
    }
  });
});
</script>

<style scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.messages-area {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.message {
  padding: 0.75rem 1rem;
  border-radius: 8px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
}

.message.user {
  background: var(--bg-secondary);
  border-left: 3px solid var(--text-primary);
}

.message.agent {
  background: var(--bg-tertiary);
  border-left: 3px solid var(--text-muted);
}

.message.system {
  background: transparent;
  border: 1px dashed var(--border-color);
  font-style: italic;
  opacity: 0.7;
}

.message-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.5rem;
  font-size: 0.65rem;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.role-label {
  font-weight: 600;
  color: var(--text-secondary);
}

.message.user .role-label { color: var(--text-primary); }
.message.agent .role-label { color: var(--text-secondary); }
.message.system .role-label { color: var(--text-muted); }

.timestamp {
  color: var(--text-muted);
  font-family: 'JetBrains Mono', monospace;
}

.message-content {
  font-size: 0.9rem;
  line-height: 1.5;
  color: var(--text-primary);
}

.message-content :deep(p) {
  margin: 0 0 0.5rem 0;
}

.message-content :deep(p:last-child) {
  margin-bottom: 0;
}

.message-content :deep(code) {
  background: var(--bg-primary);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85em;
}

.message-content :deep(strong) {
  font-weight: 600;
}

.empty-hint {
  text-align: center;
  color: var(--text-muted);
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem;
  margin-top: 2rem;
}

.blink {
  animation: blink 1s infinite;
}

@keyframes blink {
  50% { opacity: 0; }
}

/* Input Area */
.input-area {
  padding: 1rem;
  border-top: 1px solid var(--border-color);
  background: var(--bg-secondary);
}

.input-wrapper {
  display: flex;
  align-items: flex-end;
  gap: 0.5rem;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 0.5rem;
  transition: all 0.3s;
}

.input-wrapper:focus-within {
  border-color: var(--text-primary);
}

.input-wrapper.disabled {
  opacity: 0.5;
  pointer-events: none;
}

.chat-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: var(--text-primary);
  font-size: 0.9rem;
  font-family: inherit;
  resize: none;
  min-height: 24px;
  max-height: 120px;
  padding: 0.25rem 0.5rem;
}

.chat-input::placeholder {
  color: var(--text-muted);
}

.send-btn {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  border: none;
  background: var(--text-primary);
  color: var(--bg-primary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  flex-shrink: 0;
}

.send-btn:hover {
  opacity: 0.85;
}

.send-btn.stop {
  background: var(--danger);
  color: white;
}
</style>
