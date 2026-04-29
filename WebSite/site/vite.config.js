import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    port: 5173,
    strictPort: false,
    // Proxy /mcp-live → tinyassets.io/mcp in dev so the browser can
    // talk to the MCP without CORS. In prod, /wiki and /graph live on
    // tinyassets.io directly so /mcp-live → /mcp via worker config.
    proxy: {
      '/mcp-live': {
        target: 'https://tinyassets.io',
        changeOrigin: true,
        secure: true,
        rewrite: (path) => path.replace(/^\/mcp-live/, '/mcp')
      }
    }
  }
});
