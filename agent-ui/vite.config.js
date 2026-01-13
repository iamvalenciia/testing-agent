import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Load env from parent directory (../.env)
  // Third argument '' means load all variables, not just VITE_ prefixed ones
  const env = loadEnv(mode, path.resolve(__dirname, '..'), '')

  return {
    plugins: [vue()],
    define: {
      // Expose the variable to the client as VITE_GOOGLE_CLIENT_ID
      'import.meta.env.VITE_GOOGLE_CLIENT_ID': JSON.stringify(env.GOOGLE_CLIENT_ID)
    }
  }
})
