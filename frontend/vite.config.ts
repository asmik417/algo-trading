import path from 'node:path';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// Dev server on :4820 (reserved for this project). Anything under /api is forwarded to the FastAPI backend on :8000.
export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': path.resolve(__dirname, 'src') } },
  server: {
    port: 4820,
    strictPort: true,
    proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true } },
  },
});
