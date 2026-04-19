// Dual-adapter config per spec #35 §3.
// BUILD_TARGET=static → adapter-static for /, /catalog, /connect, /contribute, /legal
// BUILD_TARGET=dynamic (default) → adapter-node for /host, /status, /account

import adapterStatic from '@sveltejs/adapter-static';
import adapterNode from '@sveltejs/adapter-node';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

const target = process.env.BUILD_TARGET || 'dynamic';

const adapter = target === 'static'
  ? adapterStatic({ pages: 'build-static', assets: 'build-static', fallback: undefined, strict: false })
  : adapterNode({ out: 'build-dynamic' });

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    adapter,
    // v0: static routes prerendered; dynamic SSR on demand.
    prerender: target === 'static'
      ? { entries: ['/', '/catalog', '/connect', '/contribute', '/legal'] }
      : { entries: [] }
  }
};

export default config;
