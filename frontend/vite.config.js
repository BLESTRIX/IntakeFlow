import react from '@vitejs/plugin-react';
import { defineConfig, loadEnv } from 'vite';

// https://vite.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target:
          process.env.API_PROXY_TARGET ||
          loadEnv(mode, process.cwd(), 'API_').API_PROXY_TARGET ||
          'http://127.0.0.1:8000',
        changeOrigin: false,
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './tests/setup.js',
    include: ['tests/**/*.test.{js,jsx}'],
  },
}));
