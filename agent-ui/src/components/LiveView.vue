<template>
  <section class="live-view">
    <header class="live-view-header">
      <h2>Live View</h2>
      <div style="display: flex; align-items: center; gap: 12px;">
        <span v-if="screenshots.length" class="screenshot-count">
          {{ screenshots.length }} screenshot{{ screenshots.length !== 1 ? 's' : '' }}
        </span>
        <span v-if="isRunning" class="live-badge">REC</span>
      </div>
    </header>

    <div class="screenshot-gallery">
      <!-- Show placeholder if no screenshots -->
      <div v-if="screenshots.length === 0" class="screenshot-placeholder">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">
          <path d="M21 3H3c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h18c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 16H3V5h18v14zM4 6h2v2H4zm0 4h2v2H4zm0 4h2v2H4z"/>
        </svg>
        <span>Waiting for agent...</span>
      </div>

      <!-- Screenshot gallery - displayed right to left via CSS flex-direction: row-reverse -->
      <!-- First image (index 0) appears on the RIGHT, newest on LEFT -->
      <div
        v-for="(shot, index) in screenshots"
        :key="index"
        class="screenshot-item"
        @click="openLightbox(index)"
      >
        <span class="screenshot-step-badge">{{ index + 1 }}</span>
        <img :src="shot" alt="Screenshot" />
      </div>
    </div>

    <!-- Lightbox Modal -->
    <Teleport to="body">
      <div 
        v-if="lightboxOpen" 
        class="lightbox-overlay"
        @click.self="closeLightbox"
      >
        <div class="lightbox-content">
          <button class="lightbox-close" @click="closeLightbox">✕</button>
          
          <button 
            v-if="lightboxIndex > 0" 
            class="lightbox-nav prev"
            @click.stop="prevImage"
          >‹</button>
          
          <img :src="screenshots[lightboxIndex]" alt="Screenshot Full" />
          
          <button 
            v-if="lightboxIndex < screenshots.length - 1" 
            class="lightbox-nav next"
            @click.stop="nextImage"
          >›</button>
          
          <div class="lightbox-step-info">
            Step {{ lightboxIndex + 1 }} of {{ screenshots.length }}
          </div>
        </div>
      </div>
    </Teleport>
  </section>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  screenshot: {
    type: String,
    default: null
  },
  screenshots: {
    type: Array,
    default: () => []
  },
  isRunning: {
    type: Boolean,
    default: false
  }
})

// Lightbox state
const lightboxOpen = ref(false)
const lightboxIndex = ref(0)

function openLightbox(index) {
  lightboxIndex.value = index
  lightboxOpen.value = true
}

function closeLightbox() {
  lightboxOpen.value = false
}

function prevImage() {
  if (lightboxIndex.value > 0) {
    lightboxIndex.value--
  }
}

function nextImage() {
  if (lightboxIndex.value < props.screenshots.length - 1) {
    lightboxIndex.value++
  }
}

// Keyboard navigation
function handleKeydown(e) {
  if (!lightboxOpen.value) return
  if (e.key === 'Escape') closeLightbox()
  if (e.key === 'ArrowLeft') prevImage()
  if (e.key === 'ArrowRight') nextImage()
}

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})
</script>
