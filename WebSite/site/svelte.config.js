import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter({
      pages: 'build',
      assets: 'build',
      fallback: '404.html',
      precompress: false,
      strict: true
    }),
    paths: { base: '' },
    prerender: {
      handleHttpError: ({ path, referrer, message }) => {
        throw new Error(`prerender error at ${path} (from ${referrer}): ${message}`);
      },
      entries: ['/', '/connect', '/legal', '/goals', '/catalog', '/host', '/contribute', '/status', '/account', '/economy', '/loop', '/patterns', '/wiki', '/graph', '/alliance']
    }
  }
};

export default config;
