import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
export default defineConfig({
  plugins: [react()],
  base: '/next/',
  build: { outDir: '../symport/react_assets', emptyOutDir: true },
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8765',
        changeOrigin: true,
        configure(proxy) {
          proxy.on('proxyReq', (request) => request.removeHeader('origin'));
        },
      },
      '/session.html': { target: 'http://127.0.0.1:8765', changeOrigin: true, rewrite: () => '/' },
      '/brand': 'http://127.0.0.1:8765',
      '/phones': 'http://127.0.0.1:8765',
      '/translations.json': 'http://127.0.0.1:8765',
    },
  },
  test: { environment: 'jsdom', setupFiles: ['./src/test/setup.ts'], restoreMocks: true },
});
