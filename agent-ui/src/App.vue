<template>
  <RouterView />
</template>

<script setup>
/**
 * App.vue - Root Component
 * 
 * This component serves as the router outlet and global style container.
 * All routing is handled by vue-router (see src/router/index.js).
 * 
 * Views:
 * - /login -> LoginView.vue
 * - / -> AgentView.vue (requires auth)
 */
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

/* User Profile Styles */
.user-profile {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding-left: 0.75rem;
  margin-left: 0.5rem;
  border-left: 1px solid var(--border-color);
}

.profile-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  object-fit: cover;
  border: 2px solid var(--border-color);
  transition: all 0.2s;
}

.profile-avatar:hover {
  border-color: var(--text-primary);
  transform: scale(1.05);
}

.profile-name {
  font-size: 0.7rem;
  font-weight: 500;
  color: var(--text-secondary);
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.logout-btn {
  padding: 0.4rem !important;
  background: transparent !important;
  border-color: transparent !important;
  color: var(--text-muted) !important;
}

.logout-btn:hover {
  color: var(--danger) !important;
  background: rgba(239, 68, 68, 0.1) !important;
  border-color: rgba(239, 68, 68, 0.3) !important;
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

/* Mode Toggle */
.mode-toggle {
  display: flex !important;
  align-items: center;
  gap: 0.5rem;
  background: rgba(16, 185, 129, 0.1) !important;
  border-color: rgba(16, 185, 129, 0.3) !important;
  color: #10b981 !important;
  min-width: 110px;
  justify-content: center;
}

.mode-toggle:hover {
  background: rgba(16, 185, 129, 0.2) !important;
}

.mode-toggle.production-mode {
  background: rgba(245, 158, 11, 0.1) !important;
  border-color: rgba(245, 158, 11, 0.3) !important;
  color: #f59e0b !important;
}

.mode-toggle.production-mode:hover {
  background: rgba(245, 158, 11, 0.2) !important;
}

.mode-icon {
  font-size: 1rem;
}

.mode-label {
  font-weight: 700;
  letter-spacing: 0.5px;
  font-size: 0.7rem;
}

/* Hammer Button */
.hammer-btn {
  background: rgba(236, 72, 153, 0.1) !important;
  border-color: rgba(236, 72, 153, 0.3) !important;
  color: #ec4899 !important;
}

.hammer-btn:hover {
  background: rgba(236, 72, 153, 0.2) !important;
}
</style>
