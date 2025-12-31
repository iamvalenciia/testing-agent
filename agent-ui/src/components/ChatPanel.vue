<template>
  <section class="chat-panel">
    <header class="chat-header">
      <h2>Chat</h2>
    </header>

    <!-- Messages -->
    <div class="chat-messages" ref="messagesContainer">
      <div
        v-for="msg in messages"
        :key="msg.id"
        class="message"
        :class="msg.role"
      >
        {{ msg.content }}
      </div>

      <div v-if="messages.length === 0" class="message system">
        Send a message to start the agent...
      </div>
    </div>

    <!-- Input -->
    <div class="chat-input-container">
      <div class="chat-input-wrapper">
        <textarea
          v-model="inputText"
          class="chat-input"
          placeholder="Tell the agent what to do..."
          @keydown.enter.exact.prevent="handleSend"
          :disabled="isRunning"
          rows="1"
        ></textarea>
        <button
          class="send-button"
          @click="handleSend"
          :disabled="!inputText.trim() || isRunning"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">
            <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
          </svg>
        </button>
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'

const props = defineProps({
  messages: {
    type: Array,
    default: () => []
  },
  isRunning: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['send-message'])

const inputText = ref('')
const messagesContainer = ref(null)

function handleSend() {
  if (!inputText.value.trim() || props.isRunning) return
  emit('send-message', inputText.value)
  inputText.value = ''
}

// Auto-scroll to bottom when new messages arrive
watch(() => props.messages.length, async () => {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
})
</script>
