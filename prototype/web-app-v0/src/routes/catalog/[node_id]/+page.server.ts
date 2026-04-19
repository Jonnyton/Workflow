// Per-node detail page. v0: placeholder data; real build fetches the
// node's public-concept from Supabase (RLS handles stripping for
// non-owners).

import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ params }) => {
  return {
    node_id: params.node_id,
    // v0 stub — real build does:
    //   const { data } = await supabase.from('nodes_public_concept')
    //     .select('*').eq('node_id', params.node_id).single();
    node: {
      node_id: params.node_id,
      name: 'Placeholder node',
      domain: 'examples',
      concept: { purpose: 'v0 prototype placeholder — real build pulls from Postgres.' },
      quality: { upvote_count: 0, usage_count: 0, success_rate: null },
    },
  };
};
