// Supabase client factory — SSR-safe via @supabase/ssr
// v0: env-var-driven; real build uses SvelteKit public/private env split.

import { createServerClient, createBrowserClient } from '@supabase/ssr';

const URL = import.meta.env.VITE_SUPABASE_URL ?? '';
const ANON = import.meta.env.VITE_SUPABASE_ANON_KEY ?? '';

export function makeBrowserClient() {
  return createBrowserClient(URL, ANON);
}

export function makeServerClient(cookies: { get: (n: string) => string | undefined; set: (n: string, v: string, o: Record<string, unknown>) => void; remove: (n: string, o: Record<string, unknown>) => void }) {
  return createServerClient(URL, ANON, {
    cookies: {
      get: (name: string) => cookies.get(name),
      set: (name: string, value: string, options: Record<string, unknown>) => cookies.set(name, value, options),
      remove: (name: string, options: Record<string, unknown>) => cookies.remove(name, options),
    },
  });
}
