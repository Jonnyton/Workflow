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
    protocolVersion: '2025-06-18',
    clientInfo: { name: 'tinyassets-site-live', version: '0.1.0' },
    capabilities: {}
  });
  // Some servers require a notifications/initialized after — best effort.
  try {
    await fetch(MCP_PATH, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json, text/event-stream',
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

export type LoopStageId = 'intake' | 'investigation' | 'gate' | 'coding' | 'release' | 'observe';

export type LoopPatchRun = {
  run_id: string;
  branch_def_id: string;
  name: string;
  status: string;
  actor?: string;
  started_at?: string | null;
  finished_at?: string | null;
  last_node_id?: string;
  current_stage: LoopStageId;
  error?: string;
  failure_class?: string;
  suggested_action?: string;
};

export type LoopPatchEvent = {
  id: string;
  run_id?: string;
  stage: LoopStageId;
  status: string;
  title: string;
  detail: string;
  at?: string | null;
  node_id?: string;
  source: string;
};

export type PatchLoopFeed = {
  source: string;
  fetchedAt: string;
  live: boolean;
  overall?: string;
  branchDefId?: string;
  activeRunId?: string;
  runs: LoopPatchRun[];
  events: LoopPatchEvent[];
  warnings: string[];
};

export type PatchLoopFeedSource = 'mcp' | 'github';

const CHANGE_LOOP_BRANCH_IDS = ['fd5c66b1d87d', 'change_loop_v1'];

const KNOWN_LOOP_NODES: Record<string, LoopStageId> = {
  intake_router: 'intake',
  investigation_gate: 'investigation',
  coding_dispatch: 'coding',
  review_release_gate: 'release',
  release_safety_gate: 'release',
  live_observation_gate: 'observe',
  evolution_notes: 'observe'
};

const STAGE_TERMS: Record<LoopStageId, string[]> = {
  intake: ['intake', 'file_bug', 'file bug', 'request', 'report', 'classify', 'trigger', 'submitted', 'queued'],
  investigation: ['investigation', 'investigate', 'repro', 'root cause', 'cause', 'analysis', 'patch_packet', 'packet'],
  gate: ['gate', 'verdict', 'evidence', 'scope', 'decision', 'route', 'approved', 'rejected'],
  coding: ['coding', 'code', 'dev', 'writer', 'auto-fix', 'implement', 'patch', 'branch', 'diff', 'pr'],
  release: ['release', 'review', 'merge', 'ship', 'deploy', 'production', 'website', 'rollback', 'landed'],
  observe: ['observe', 'observation', 'watch', 'canary', 'monitor', 'ratify', 'user_sim', 'clean use']
};

function stringify(value: unknown): string {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  try {
    return JSON.stringify(value);
  } catch {
    return '';
  }
}

function isSparseText(value: string): boolean {
  const text = value.trim();
  return !text || text === '{}' || text === '[]' || text === 'null' || text === 'undefined';
}

function firstString(...values: unknown[]): string {
  for (const value of values) {
    const text = stringify(value).trim();
    if (text) return text;
  }
  return '';
}

function firstDetailString(...values: unknown[]): string {
  for (const value of values) {
    const text = stringify(value).trim();
    if (!isSparseText(text)) return text;
  }
  return '';
}

function normalizeTimestamp(value: unknown): string | null {
  const text = firstString(value);
  if (!text) return null;
  if (typeof value === 'number' || /^\d+(\.\d+)?$/.test(text)) {
    const numeric = Number(text);
    if (Number.isFinite(numeric)) {
      const millis = numeric > 1_000_000_000_000 ? numeric : numeric * 1000;
      const date = new Date(millis);
      if (!Number.isNaN(date.getTime())) return date.toISOString();
    }
  }
  const parsed = Date.parse(text);
  if (!Number.isNaN(parsed)) return new Date(parsed).toISOString();
  return text;
}

function humanizeNodeId(value: unknown): string {
  const text = firstString(value);
  if (!text) return '';
  return text
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function inferLoopStage(...values: unknown[]): LoopStageId {
  for (const value of values) {
    const text = stringify(value).toLowerCase();
    for (const [nodeId, stage] of Object.entries(KNOWN_LOOP_NODES) as Array<[string, LoopStageId]>) {
      if (text === nodeId || text.includes(nodeId)) return stage;
    }
  }
  const haystack = values.map(stringify).join(' ').toLowerCase();
  for (const [stage, terms] of Object.entries(STAGE_TERMS) as Array<[LoopStageId, string[]]>) {
    if (terms.some((term) => haystack.includes(term))) return stage;
  }
  return 'intake';
}

function normalizeRun(raw: any): LoopPatchRun {
  const runId = firstString(raw?.run_id, raw?.id, raw?.runId);
  const branchDefId = firstString(raw?.branch_def_id, raw?.branchDefId, raw?.branch_id, raw?.workflow, raw?.branch);
  const name = firstString(raw?.run_name, raw?.name, raw?.title, runId);
  const lastNode = firstString(raw?.last_node_id, raw?.lastNodeId, raw?.node_id, raw?.current_node);
  const status = firstString(raw?.status, raw?.state, 'unknown').toLowerCase();
  const error = firstDetailString(raw?.error, raw?.failure, raw?.exception);

  return {
    run_id: runId,
    branch_def_id: branchDefId,
    name,
    status,
    actor: firstString(raw?.actor, raw?.author, raw?.claimed_by) || undefined,
    started_at: normalizeTimestamp(raw?.started_at ?? raw?.startedAt ?? raw?.created_at),
    finished_at: normalizeTimestamp(raw?.finished_at ?? raw?.finishedAt ?? raw?.completed_at),
    last_node_id: lastNode,
    current_stage: inferLoopStage(lastNode, name, status, error),
    error: error || undefined,
    failure_class: firstString(raw?.failure_class, raw?.failureClass) || undefined,
    suggested_action: firstDetailString(raw?.suggested_action, raw?.suggestedAction) || undefined
  };
}

function normalizeEvent(raw: any, index: number, run?: LoopPatchRun): LoopPatchEvent {
  const runId = firstString(raw?.run_id, raw?.runId, run?.run_id);
  const nodeId = firstString(raw?.node_id, raw?.nodeId, raw?.node, raw?.step, raw?.stage);
  const status = firstString(raw?.status, raw?.state, raw?.event_type, raw?.type, run?.status, 'event').toLowerCase();
  const title = firstString(raw?.title, raw?.label, humanizeNodeId(nodeId), raw?.event_type, raw?.type, 'Loop event');
  const detail = firstDetailString(
    raw?.detail,
    raw?.message,
    raw?.text,
    raw?.summary,
    raw?.output_summary,
    raw?.error,
    raw?.patch_title,
    run?.name,
    'Loop state changed.'
  );
  const step = firstString(raw?.step_index, raw?.index, index);
  const fallbackDetail = run?.error
    ? `${status === 'pending' ? 'Pending when run failed' : 'Run failed'}: ${run.error}`
    : `${title} is ${status}.`;

  return {
    id: firstString(raw?.event_id, raw?.id, `${runId || 'loop'}:${step}:${nodeId || title}`),
    run_id: runId || undefined,
    stage: inferLoopStage(raw?.stage, nodeId, title, detail, status, run?.error),
    status,
    title,
    detail: detail || fallbackDetail,
    at: normalizeTimestamp(raw?.created_at ?? raw?.timestamp ?? raw?.at ?? raw?.started_at ?? run?.started_at),
    node_id: nodeId || undefined,
    source: firstString(raw?.source, 'MCP run event')
  };
}

function runLooksLikePatchLoop(run: LoopPatchRun): boolean {
  const text = `${run.branch_def_id} ${run.name} ${run.last_node_id ?? ''}`.toLowerCase();
  return CHANGE_LOOP_BRANCH_IDS.some((id) => text.includes(id.toLowerCase())) ||
    text.includes('change_loop') ||
    text.includes('patch') ||
    text.includes('bug_investigation');
}

function activeRun(runs: LoopPatchRun[]): LoopPatchRun | undefined {
  return runs.find((run) => !['completed', 'failed', 'cancelled', 'canceled'].includes(run.status)) ?? runs[0];
}

function mergeRunSnapshot(run: LoopPatchRun | undefined, snapshot: any): void {
  if (!run || !snapshot || typeof snapshot !== 'object') return;
  run.error = firstDetailString(snapshot.error, snapshot.failure, snapshot.exception, run.error) || undefined;
  run.failure_class = firstString(snapshot.failure_class, snapshot.failureClass, run.failure_class) || undefined;
  run.suggested_action = firstDetailString(snapshot.suggested_action, snapshot.suggestedAction, run.suggested_action) || undefined;
  run.finished_at = normalizeTimestamp(snapshot.finished_at ?? snapshot.finishedAt ?? snapshot.completed_at) ?? run.finished_at;
  run.started_at = normalizeTimestamp(snapshot.started_at ?? snapshot.startedAt ?? snapshot.created_at) ?? run.started_at;
  run.last_node_id = firstString(snapshot.last_node_id, snapshot.lastNodeId, snapshot.node_id, run.last_node_id) || run.last_node_id;
  run.current_stage = inferLoopStage(run.last_node_id, run.name, run.status, run.error);
}

function normalizeLoopToolFeed(raw: any): PatchLoopFeed | null {
  const body = raw?.feed ?? raw?.result ?? raw;
  if (!body || typeof body !== 'object') return null;

  const runs = Array.isArray(body.runs) ? body.runs.map(normalizeRun) : [];
  const directEvents = Array.isArray(body.events) ? body.events : [];
  const patchEvents = Array.isArray(body.patches)
    ? body.patches.flatMap((patch: any) => {
        const events = Array.isArray(patch?.events) ? patch.events : [];
        return events.map((event: any) => ({
          ...event,
          run_id: event?.run_id ?? patch?.run_id ?? patch?.id,
          patch_title: event?.patch_title ?? patch?.title ?? patch?.name
        }));
      })
    : [];
  const selectedRun = activeRun(runs);
  const events = [...directEvents, ...patchEvents].map((event, index) => normalizeEvent(event, index, selectedRun));

  if (!runs.length && !events.length) return null;

  return {
    source: firstString(body.source, 'MCP loop action=feed'),
    fetchedAt: firstString(body.fetched_at, body.fetchedAt, new Date().toISOString()),
    live: true,
    branchDefId: firstString(body.branch_def_id, selectedRun?.branch_def_id, CHANGE_LOOP_BRANCH_IDS[0]),
    activeRunId: firstString(body.active_run_id, body.activeRunId, selectedRun?.run_id) || undefined,
    runs,
    events,
    warnings: []
  };
}

function warningText(prefix: string, error: unknown): string {
  return `${prefix}: ${error instanceof Error ? error.message : stringify(error) || 'unavailable'}`;
}

type CommunityLoopWatchStage = {
  name: string;
  status: string;
  summary: string;
  evidence?: string | null;
  url?: string | null;
  details?: Record<string, any>;
};

type CommunityLoopWatchStatus = {
  version?: number;
  checked_at?: string;
  repo?: string | null;
  overall?: string;
  stages?: CommunityLoopWatchStage[];
};

function jsonFromMarkdown(text: string): CommunityLoopWatchStatus | null {
  const blocks = Array.from(text.matchAll(/```json\s*([\s\S]*?)```/gi)).map((match) => match[1]?.trim()).filter(Boolean);
  for (const block of blocks.reverse()) {
    try {
      const parsed = JSON.parse(block);
      if (parsed?.stages && Array.isArray(parsed.stages)) return parsed;
    } catch {}
  }
  try {
    const parsed = JSON.parse(text);
    if (parsed?.stages && Array.isArray(parsed.stages)) return parsed;
  } catch {}
  return null;
}

function communityStatusToFeed(status: CommunityLoopWatchStatus, source: string, warnings: string[] = []): PatchLoopFeed {
  const checkedAt = status.checked_at ?? new Date().toISOString();
  const stages = Array.isArray(status.stages) ? status.stages : [];
  const events = stages.map((stage, index): LoopPatchEvent => ({
    id: `community-loop:${stage.name}:${index}`,
    stage: inferLoopStage(stage.name, stage.summary, stage.evidence, stage.details),
    status: (stage.status || 'unknown').toLowerCase(),
    title: stage.name || 'Loop watch stage',
    detail: [stage.summary, stage.evidence].filter(Boolean).join(' · ') || 'Community loop watch stage updated.',
    at: checkedAt,
    node_id: stage.name,
    source: stage.url ?? source
  }));

  return {
    source,
    fetchedAt: checkedAt,
    live: true,
    overall: status.overall ?? 'unknown',
    branchDefId: CHANGE_LOOP_BRANCH_IDS[0],
    runs: [],
    events,
    warnings
  };
}

async function fetchJsonIfAvailable(url: string): Promise<CommunityLoopWatchStatus | null> {
  const res = await fetchWithTimeout(url, { cache: 'no-store' });
  if (!res.ok) return null;
  const parsed = await res.json();
  if (parsed?.stages && Array.isArray(parsed.stages)) return parsed;
  return null;
}

async function fetchWithTimeout(url: string, init: RequestInit = {}, timeoutMs = 6500): Promise<Response> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    window.clearTimeout(timer);
  }
}

async function fetchCommunityLoopWatchFeed(warnings: string[]): Promise<PatchLoopFeed | null> {
  try {
    const localStatus = await fetchJsonIfAvailable('/community-loop-status.json');
    if (localStatus) return communityStatusToFeed(localStatus, 'community-loop-status.json', warnings);
  } catch (error) {
    warnings.push(warningText('community-loop-status.json', error));
  }

  try {
    const issuesRes = await fetchWithTimeout('https://api.github.com/repos/Jonnyton/Workflow/issues?state=open&labels=community-loop-red&per_page=1', {
      headers: { Accept: 'application/vnd.github+json' }
    });
    if (!issuesRes.ok) throw new Error(`GitHub issues ${issuesRes.status}`);
    const issues = await issuesRes.json();
    const issue = Array.isArray(issues) ? issues[0] : null;
    if (issue) {
      const bodies: string[] = [];
      if (typeof issue.body === 'string') bodies.push(issue.body);
      if (issue.comments_url) {
        try {
          const commentsRes = await fetchWithTimeout(`${issue.comments_url}?per_page=10`, {
            headers: { Accept: 'application/vnd.github+json' }
          });
          if (commentsRes.ok) {
            const comments = await commentsRes.json();
            if (Array.isArray(comments)) {
              for (const comment of comments.slice(-10)) {
                if (typeof comment.body === 'string') bodies.push(comment.body);
              }
            }
          }
        } catch (error) {
          warnings.push(warningText('community-loop-red comments', error));
        }
      }
      for (const body of bodies.reverse()) {
        const parsed = jsonFromMarkdown(body);
        if (parsed) return communityStatusToFeed(parsed, issue.html_url ?? 'GitHub community-loop-red issue', warnings);
      }
      warnings.push('community-loop-red issue exists but no status JSON was visible yet');
    }
  } catch (error) {
    warnings.push(warningText('community-loop-red issue', error));
  }

  try {
    const workflowsRes = await fetchWithTimeout('https://api.github.com/repos/Jonnyton/Workflow/actions/workflows?per_page=100', {
      headers: { Accept: 'application/vnd.github+json' }
    });
    if (!workflowsRes.ok) throw new Error(`GitHub workflows ${workflowsRes.status}`);
    const workflowsPayload = await workflowsRes.json();
    const workflows = Array.isArray(workflowsPayload?.workflows) ? workflowsPayload.workflows : [];
    const workflow = workflows.find((candidate: any) => String(candidate?.path ?? '').endsWith('/community-loop-watch.yml'));
    if (!workflow?.id) {
      warnings.push('community-loop-watch workflow is not published on GitHub yet');
      return null;
    }

    const runsRes = await fetchWithTimeout(`https://api.github.com/repos/Jonnyton/Workflow/actions/workflows/${workflow.id}/runs?per_page=1`, {
      headers: { Accept: 'application/vnd.github+json' }
    });
    if (!runsRes.ok) throw new Error(`GitHub workflow runs ${runsRes.status}`);
    const payload = await runsRes.json();
    const run = Array.isArray(payload?.workflow_runs) ? payload.workflow_runs[0] : null;
    if (run) {
      return communityStatusToFeed(
        {
          checked_at: run.updated_at ?? run.created_at,
          overall: run.conclusion === 'success' ? 'green' : run.status === 'completed' ? 'red' : 'yellow',
          stages: [
            {
              name: 'Community loop watch',
              status: run.conclusion === 'success' ? 'green' : run.status === 'completed' ? 'red' : 'yellow',
              summary: `latest workflow run is ${run.status}${run.conclusion ? `/${run.conclusion}` : ''}`,
              evidence: run.html_url,
              url: run.html_url
            }
          ]
        },
        'GitHub Actions community-loop-watch.yml',
        warnings
      );
    }
  } catch (error) {
    warnings.push(warningText('community-loop-watch workflow', error));
  }

  return null;
}

async function fetchMcpPatchLoopFeed(limit: number, warnings: string[]): Promise<PatchLoopFeed> {
  try {
    const loopFeed = normalizeLoopToolFeed(await callTool('loop', { action: 'feed', limit }));
    if (loopFeed) return loopFeed;
    warnings.push('loop action=feed returned no loop events yet');
  } catch (error) {
    warnings.push(warningText('loop action=feed', error));
  }

  try {
    const branchFeed = await callTool('extensions', {
      action: 'list_runs',
      branch_def_id: CHANGE_LOOP_BRANCH_IDS[0],
      limit
    });
    let runs = Array.isArray(branchFeed?.runs) ? branchFeed.runs.map(normalizeRun) : [];

    if (!runs.length) {
      const allFeed = await callTool('extensions', { action: 'list_runs', limit: Math.max(limit, 24) });
      runs = Array.isArray(allFeed?.runs) ? allFeed.runs.map(normalizeRun).filter(runLooksLikePatchLoop) : [];
    }

    const selectedRun = activeRun(runs);
    let events: LoopPatchEvent[] = [];

    if (selectedRun?.run_id) {
      let runSnapshot: any = null;
      try {
        const streamed = await callTool('extensions', {
          action: 'stream_run',
          run_id: selectedRun.run_id,
          since_step: -1
        });
        events = Array.isArray(streamed?.events)
          ? streamed.events.map((event: any, index: number) => normalizeEvent(event, index, selectedRun))
          : [];
      } catch (error) {
        warnings.push(warningText('extensions stream_run', error));
      }

      if (!events.length || selectedRun.status.includes('fail') || events.every((event) => isSparseText(event.detail))) {
        try {
          runSnapshot = await callTool('extensions', {
            action: 'get_run',
            run_id: selectedRun.run_id
          });
          mergeRunSnapshot(selectedRun, runSnapshot);
          const rawEvents = runSnapshot?.events ?? runSnapshot?.timeline ?? runSnapshot?.steps ?? [];
          if (!events.length) {
            events = Array.isArray(rawEvents)
            ? rawEvents.map((event: any, index: number) => normalizeEvent(event, index, selectedRun))
            : [];
          }
        } catch (error) {
          warnings.push(warningText('extensions get_run', error));
        }
      }

      if (selectedRun.error) {
        events = events.map((event) => ({
          ...event,
          detail: isSparseText(event.detail)
            ? `${event.status === 'pending' ? 'Pending when run failed' : 'Run failed'}: ${selectedRun.error}`
            : event.detail
        }));
        if (!events.some((event) => event.status.includes('fail') || event.detail.includes(selectedRun.error ?? ''))) {
          events.push({
            id: `${selectedRun.run_id}:failure`,
            run_id: selectedRun.run_id,
            stage: inferLoopStage(selectedRun.last_node_id, selectedRun.error, selectedRun.failure_class),
            status: 'failed',
            title: 'Run failed',
            detail: [
              selectedRun.error,
              selectedRun.failure_class ? `class: ${selectedRun.failure_class}` : '',
              selectedRun.suggested_action ? `next: ${selectedRun.suggested_action}` : ''
            ].filter(Boolean).join(' · '),
            at: selectedRun.finished_at ?? selectedRun.started_at ?? null,
            node_id: selectedRun.last_node_id,
            source: 'MCP extensions get_run'
          });
        }
      }
    }

    return {
      source: 'MCP extensions list_runs/stream_run',
      fetchedAt: new Date().toISOString(),
      live: true,
      branchDefId: selectedRun?.branch_def_id || CHANGE_LOOP_BRANCH_IDS[0],
      activeRunId: selectedRun?.run_id,
      runs,
      events: events.slice(-36),
      warnings
    };
  } catch (error) {
    warnings.push(warningText('extensions list_runs', error));
  }

  return {
    source: 'waiting for MCP loop feed',
    fetchedAt: new Date().toISOString(),
    live: false,
    branchDefId: CHANGE_LOOP_BRANCH_IDS[0],
    runs: [],
    events: [],
    warnings
  };
}

export async function fetchPatchLoopFeed(limit = 12, source: PatchLoopFeedSource = 'mcp'): Promise<PatchLoopFeed> {
  const warnings: string[] = [];

  if (source === 'github') {
    const communityWatch = await fetchCommunityLoopWatchFeed(warnings);
    if (communityWatch) return communityWatch;
    return {
      source: 'waiting for community-loop-watch',
      fetchedAt: new Date().toISOString(),
      live: false,
      branchDefId: CHANGE_LOOP_BRANCH_IDS[0],
      runs: [],
      events: [],
      warnings
    };
  }

  return fetchMcpPatchLoopFeed(limit, warnings);
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

  // Dedup by canonical id/slug — live MCP sometimes returns case variants
  // (e.g. BUG-003-... and bug-003-...) that pad to the same canonical id.
  // Without this dedup, Svelte's keyed {#each} blocks throw each_key_duplicate.
  function dedupBy<T>(arr: T[], keyFn: (x: T) => string): T[] {
    const seen = new Set<string>();
    const out: T[] = [];
    for (const item of arr) {
      const k = keyFn(item);
      if (seen.has(k)) continue;
      seen.add(k);
      out.push(item);
    }
    return out;
  }
  wiki.bugs = dedupBy(wiki.bugs, (b: any) => b.id);
  wiki.concepts = dedupBy(wiki.concepts, (c: any) => c.slug);
  wiki.notes = dedupBy(wiki.notes, (n: any) => n.slug);
  wiki.plans = dedupBy(wiki.plans, (pl: any) => pl.slug);
  wiki.drafts = dedupBy(wiki.drafts, (d: any) => d.slug);

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
