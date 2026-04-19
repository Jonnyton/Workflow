// /account SSR — auth-gated. v0 stub; real build reads Supabase session + data.

import { redirect } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals }) => {
  if (!locals.user) {
    throw redirect(302, '/connect');
  }
  return {
    user: locals.user,
    // real: myExports via export sync status; deleteEligible true always.
  };
};
