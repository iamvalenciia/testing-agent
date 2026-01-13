/**
 * UI Store
 * Manages theme, modal state, and toasts.
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useUiStore = defineStore('ui', () => {
    // Theme
    const isDark = ref(localStorage.getItem('theme') !== 'light')

    function toggleTheme() {
        isDark.value = !isDark.value
        localStorage.setItem('theme', isDark.value ? 'dark' : 'light')
    }

    // Modals
    const activeModal = ref(null) // 'workflow' | 'success' | 'staticData' | 'hammer' | 'report' | null
    const isSaving = ref(false)

    function openModal(modalName) {
        activeModal.value = modalName
    }

    function closeModal() {
        activeModal.value = null
        isSaving.value = false
    }

    // Toast
    const toast = ref(null)
    let toastTimeout = null

    function showToast(message, type = 'info', duration = 3000) {
        if (toastTimeout) clearTimeout(toastTimeout)
        toast.value = { message, type }
        toastTimeout = setTimeout(() => {
            toast.value = null
        }, duration)
    }

    return {
        // State
        isDark,
        activeModal,
        isSaving,
        toast,
        // Actions
        toggleTheme,
        openModal,
        closeModal,
        showToast,
    }
})
