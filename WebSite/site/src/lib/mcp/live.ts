/**
 * Browser-side live MCP client.
 *
 * In dev: fetch hits /mcp-live → vite proxy → https://tinyassets.io/mcp
 * In prod: fetch hits /mcp directly (same origin as the deployed site).
 *
 * Uses raw JSON-RPC over HTTP — simpler than dragging the full SDK into the
 * browser bundle, and the gateway at tinyassets.io accepts plain
 * `Content-Type: application/json` POSTs.
 */

import type { Snapshot } from '$lib/mcp/types';

const MCP_PATH = import.meta.env.DEV ? '/mcp-live' : '/mcp';

let initialized = false;
let sessionId: string | null = null;
let nextId = 1;

type RpcResp = { jsonrpc: '2.0'; id: number; result?: any; error?: { code: number; message: string } };

async function rpc(method: string, params: any = {}): Promise<any> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/json, text/event-stream'
  };
  if (sessionId) headers['Mcp-Session-Id'] = sessionId;

  const body = { jsonrpc: '2.0', id: nextId++, method, params };
  const res = await fetch(MCP_PATH, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
    credentials: 'omit'
  });

  // Capture session id on first call
  const sid = res.headers.get('Mcp-Session-Id');
  if (sid && !sessionId) sessionId = sid;

  if (!res.ok) throw new Error(`MCP HTTP ${res.status}: ${res.statusText}`);

  // Some gateways return text/event-stream; parse first data line.
  const ct = res.headers.get('Content-Type') ?? '';
  let text = await res.text();
  if (ct.includes('text/event-stream')) {
    const dataLine = text.split('\n').find((l) => l.startsWith('data:'));
    if (!dataLine) throw new Error('SSE response missing data line');
    text = dataLine.replace(/^data:\s*/, '');
  }

  const json = JSON.parse(text) as RpcResp;
  if (json.error) throw new Error(`MCP error ${json.error.code}: ${json.error.message}`);
  return json.result;
}

async function ensureInit(): Promise<void> {
  if (initialized) return;
  await rpc('initialize', {
    protocolVersion: '2024-11-05',
    capabilities: {},
    clientInfo: { name: 'tinyassets-site-live', version: '0.1.0' }
  });
  // Some servers require a notifications/initialized after — best effort.
  try {
    await fetch(MCP_PATH, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        ...(sessionId ? { 'Mcp-Session-Id': sessionId } : {})
      },
      body: JSON.stringify({ jsonrpc: '2.0', method: 'notifications/initialized' })
    });
  } catch {}
  initialized = true;
}

async function callTool(name: string, args: Record<string, any>): Promise<any> {
  await ensureInit();
  const result = await rpc('tools/call', { name, arguments: args });
  // result.content is [{ type: 'text', text: '<json>' }, ...]
  const t = result?.content?.find((c: any) => c?.type === 'text');
  if (!t?.text) return null;
  try {
    const parsed = JSON.parse(t.text);
    if (parsed && typeof parsed.result === 'string') {
      try { return JSON.parse(parsed.result); } catch { return parsed.result; }
    }
    return parsed;
  } catch {
    return t.text;
  }
}

// ============ Public surface ============

export type LiveResult = {
  goals: any[];
  universes: any[];
  wiki: { promoted: any[]; drafts: any[] };
  fetchedAt: string;
};

/** Fetch the same data the snapshot bakes — but live. */
export async function fetchLive(): Promise<LiveResult> {
  const [wikiList, goalsList, universesList] = await Promise.all([
    callTool('wiki', { action: 'list' }),
    callTool('goals', { action: 'list' }),
    callTool('universe', { action: 'list' })
  ]);
  return {
    goals: goalsList?.goals ?? [],
    universes: universesList?.universes ?? [],
    wiki: {
      promoted: wikiList?.promoted ?? [],
      drafts: wikiList?.drafts ?? []
    },
    fetchedAt: new Date().toISOString()
  };
}

/** Fetch a single page's body (for ref-extraction). */
export async function fetchPageBody(page: string): Promise<{ content?: string } | null> {
  return await callTool('wiki', { action: 'read', page: page.replace(/\.md$/, '') });
}

/** Shape the live raw response into the same structure /wiki + /graph use from the snapshot. */
export function liveToSnapshotShape(live: LiveResult, baked: Snapshot): Snapshot {
  // Reuse the baked snapshot's edges + tags (which were extracted from page
  // bodies at snapshot time). For real-time edge extraction we'd need to
  // crawl bodies in the browser too — done in fetchEdges() separately.
  const wiki = { bugs: [] as any[], concepts: [] as any[], notes: [] as any[], plans: [] as any[], drafts: [] as any[], other: [] as any[] };
  for (const p of live.wiki.promoted) {
    const path = p.path ?? '';
    const title = p.title ?? path;
    if (path.includes('/bugs/')) {
      const m = path.match(/BUG-?(\d+)/i);
      const id = m ? `BUG-${m[1].padStart(3, '0')}` : path;
      wiki.bugs.push({ id, title, slug: path });
    } else if (path.startsWith('drafts/')) {
      wiki.other.push({ slug: path, title });
    } else if (path.includes('/concepts/')) {
      wiki.concepts.push({ slug: path, title });
    } else if (path.includes('/notes/')) {
      wiki.notes.push({ slug: path, title });
    } else if (path.includes('/plans/')) {
      wiki.plans.push({ slug: path, title });
    }
  }
  for (const p of live.wiki.drafts) {
    wiki.drafts.push({ slug: p.path ?? '', title: p.title ?? p.path });
  }

  const promoted = wiki.bugs.length + wiki.concepts.length + wiki.notes.length + wiki.plans.length + wiki.other.length;

  return {
    fetched_at: live.fetchedAt,
    source: 'tinyassets.io/mcp · live',
    stats: {
      wiki_promoted: promoted,
      wiki_drafts: wiki.drafts.length,
      goals: live.goals.length,
      universes: live.universes.length,
      edges: baked.edges?.length ?? 0
    },
    goals: live.goals.map((g) => ({
      id: g.goal_id ?? g.id,
      name: g.name ?? '',
      summary: g.description ?? '',
      tags: typeof g.tags === 'string' ? g.tags.split(',').map((t: string) => t.trim()).filter(Boolean) : (g.tags ?? []),
      author: g.author ?? 'anonymous',
      visibility: g.visibility ?? 'public'
    })),
    universes: live.universes.map((u) => ({
      id: u.id,
      phase: u.phase_human ?? u.phase ?? 'unknown',
      word_count: u.word_count ?? 0,
      last_activity_at: u.last_activity_at ?? null,
      accept_rate: u.accept_rate ?? null
    })),
    wiki,
    edges: baked.edges ?? [],
    tags: baked.tags ?? {}
  };
}
