<template>
  <div 
    class="group flex w-full gap-4 px-4 py-6 text-gray-800 dark:text-gray-100 border-b border-gray-100 dark:border-zinc-900/50 last:border-0"
    :class="[isUser ? 'bg-white dark:bg-zinc-950' : 'bg-gray-50/50 dark:bg-zinc-900/20']"
  >
    <!-- Avatar -->
    <div class="flex-shrink-0 flex flex-col relative items-end">
      <div 
        class="w-8 h-8 rounded-lg flex items-center justify-center shadow-sm ring-1 ring-inset"
        :class="[
          isUser 
            ? 'bg-white dark:bg-zinc-800 ring-gray-200 dark:ring-zinc-700 text-gray-500' 
            : 'bg-indigo-600 dark:bg-indigo-500 ring-indigo-600 dark:ring-indigo-500 text-white'
        ]"
      >
        <UserIcon v-if="isUser" class="w-5 h-5" />
        <BotIcon v-else class="w-5 h-5" />
      </div>
    </div>

    <!-- Content -->
    <div class="relative flex-1 overflow-hidden min-w-0">
      <!-- Name & Time -->
      <div class="flex items-center gap-2 mb-1">
        <span class="font-semibold text-sm text-gray-900 dark:text-gray-100">
          {{ isUser ? 'You' : 'Agent' }}
        </span>
        <span class="text-xs text-gray-400 dark:text-zinc-500">
          {{ message.timestamp }}
        </span>
      </div>

      <!-- Thinking Process (Agent Only) -->
      <div v-if="!isUser && hasSteps" class="mb-4">
        <div class="rounded-lg border border-gray-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/50 overflow-hidden">
          <button 
            @click="isExpanded = !isExpanded"
            class="w-full flex items-center gap-2 px-3 py-2 text-xs font-medium text-gray-500 dark:text-zinc-400 hover:bg-gray-50 dark:hover:bg-zinc-800/50 transition-colors"
          >
            <component :is="isExpanded ? ChevronDownIcon : ChevronRightIcon" class="w-4 h-4" />
            <span v-if="isThinking && !isExpanded" class="animate-pulse">Thinking...</span>
            <span v-else>Process Log ({{ message.steps.length }} steps)</span>
          </button>
          
          <div v-if="isExpanded" class="border-t border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950/30 p-3 space-y-3">
            <div v-for="(step, index) in message.steps" :key="index" class="relative pl-4 border-l mb-2 border-gray-200 dark:border-zinc-800 last:mb-0">
              <!-- Step content -->
              <div class="text-xs text-gray-600 dark:text-zinc-300 mb-1">
                <span class="font-mono text-gray-400 dark:text-zinc-500 mr-2">[{{ index + 1 }}]</span>
                <span class="font-medium">{{ step.name || 'Action' }}</span>
              </div>
              
              <!-- Logs/Details -->
              <div v-if="step.url" class="text-[10px] font-mono text-gray-400 truncate mb-1">
                {{ step.url }}
              </div>

               <!-- Embedded Screenshot -->
              <div v-if="step.screenshot" class="mt-2 group/image inline-block relative">
                 <img 
                  :src="step.screenshot" 
                  alt="Action Screenshot" 
                  class="h-20 w-auto rounded border border-gray-200 dark:border-zinc-700 cursor-pointer hover:scale-105 transition-transform"
                  @click="$emit('view-image', step.screenshot)"
                />
              </div>
            </div>

             <!-- Loading Indicator for Thinking -->
             <div v-if="isThinking" class="pl-4 border-l border-gray-200 dark:border-zinc-800 py-1">
                <span class="inline-block w-2 h-2 bg-indigo-500 rounded-full animate-bounce"></span>
             </div>
          </div>
        </div>
      </div>

      <!-- Main Message Content -->
      <div 
        class="prose prose-sm dark:prose-invert max-w-none prose-p:leading-relaxed prose-pre:bg-gray-50 dark:prose-pre:bg-zinc-900 prose-pre:border prose-pre:border-gray-200 dark:prose-pre:border-zinc-800"
        v-html="renderedContent"
      ></div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { marked } from 'marked'
import { 
  User as UserIcon, 
  Bot as BotIcon, 
  ChevronDown as ChevronDownIcon, 
  ChevronRight as ChevronRightIcon 
} from 'lucide-vue-next'

const props = defineProps({
  message: {
    type: Object,
    required: true
  },
  isThinking: {
    type: Boolean,
    default: false
  }
})

defineEmits(['view-image'])

const isUser = computed(() => props.message.role === 'user')
const hasSteps = computed(() => props.message.steps && props.message.steps.length > 0)
const isExpanded = ref(false)

// Expand automatically if thinking
if (props.isThinking) {
  isExpanded.value = true
}

const renderedContent = computed(() => {
  if (!props.message.content) return ''
  // Safety check for empty content
  return marked(props.message.content)
})
</script>
