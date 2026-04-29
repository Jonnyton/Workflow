// node-detail.jsx
// Right-side drawer: when a user clicks a node on any diagram, this opens
// with state schema, lifecycle position, downstream effects.

const NODE_LIBRARY = {
  // Dev-team
  lead:       { kind: "indigo", label: "lead", role: "Coordinator", reads: ["project_brief", "acceptance_criteria"], writes: ["task_list", "current_task"], lifecycle: "WORKING (orchestration)", description: "Decomposes the brief. Holds the retry budget. Re-issues tasks when a check fails and the failure is recoverable." },
  researcher: { kind: "sage",   label: "researcher", role: "Discovery", reads: ["task_list"], writes: ["research_notes"], lifecycle: "WORKING (independent)", description: "Roams the canon. Returns with citations and prior-art summaries. Runs in parallel with the architect." },
  architect:  { kind: "sage",   label: "architect", role: "Discovery", reads: ["task_list"], writes: ["api_contract", "schema"], lifecycle: "WORKING (independent)", description: "Drafts the public surface — endpoints, types, contracts. Independent of researcher; both feed the planner." },
  planner:    { kind: "sage",   label: "planner", role: "Planning", reads: ["research_notes", "api_contract"], writes: ["plan", "subtasks"], lifecycle: "WORKING (synthesis)", description: "Fan-in barrier — waits for both researcher and architect. Slices the work into discipline-specific subtasks." },
  dev:        { kind: "sage",   label: "dev", role: "Implementation", reads: ["current_task"], writes: ["implementation"], lifecycle: "WORKING (heavy)", description: "Writes code. The only place tokens are heavily spent in the 3-node lineup." },
  frontend_dev:{ kind: "sage",  label: "frontend_dev", role: "Implementation", reads: ["plan"], writes: ["fe_diff"], lifecycle: "WORKING (parallel)", description: "Ships UI. Parallel with backend_dev and db_dev." },
  backend_dev:{ kind: "sage",   label: "backend_dev", role: "Implementation", reads: ["plan"], writes: ["be_diff"], lifecycle: "WORKING (parallel)", description: "Ships API + service code. Parallel with frontend_dev and db_dev." },
  db_dev:     { kind: "sage",   label: "db_dev", role: "Implementation", reads: ["plan"], writes: ["migration"], lifecycle: "WORKING (parallel)", description: "Schema + migration scripts. Parallel with frontend_dev and backend_dev." },
  checker:    { kind: "amber",  label: "checker", role: "Quality", reads: ["implementation", "acceptance_criteria"], writes: ["check_result"], lifecycle: "WORKING (judgment)", description: "Runs the rubric. Produces a structured verdict (PASS / FAIL_X). The gate routes on it." },
  tester:     { kind: "amber",  label: "tester", role: "Quality", reads: ["fe_diff", "be_diff", "migration"], writes: ["test_report"], lifecycle: "WORKING (parallel)", description: "All three * _dev diffs feed in. Tester runs once their inputs are populated, not once per dev." },
  reviewer:   { kind: "amber",  label: "reviewer", role: "Quality", reads: ["fe_diff", "be_diff", "migration"], writes: ["review_notes"], lifecycle: "WORKING (parallel)", description: "Code-quality and security review. Independent from tester; both fan into checker." },
  gate:       { kind: "ember",  label: "gate", role: "Routing decision", reads: ["check_result", "retry_count"], writes: ["gate_decision"], lifecycle: "WORKING (decision)", description: "Emits a decision string the outer runner interprets — END | LOOP_TO:<node> | SOFT_ESCALATE. The gate doesn't loop inside the workflow; the outer runner does." },
  docs:       { kind: "violet", label: "docs", role: "Distribution", reads: ["implementation"], writes: ["readme", "changelog"], lifecycle: "WORKING (post-pass)", description: "Runs only after gate emits PASS. Writes user-facing artifacts." },
  // Book pipeline
  scribe:     { kind: "violet", label: "Scribe", role: "Prose generation", reads: ["scene_plan", "canon_context", "prior_state"], writes: ["draft"], lifecycle: "WORKING (generative)", description: "Drafts the scene. Loops back from the critique gate with the critique appended as context — not a fresh prompt." },
  lorekeeper: { kind: "violet", label: "Lorekeeper", role: "Canon retrieval", reads: ["scene_request"], writes: ["canon_context"], lifecycle: "WORKING (retrieval)", description: "Roams the canon graph. Returns prompt-ready excerpts with citations." },
  architect_b:{ kind: "violet", label: "Architect", role: "Scene structure", reads: ["chapter_plan"], writes: ["scene_plan"], lifecycle: "WORKING (planning)", description: "Beats the scene before the Scribe writes prose. Outputs structure, not language." },
  critique:   { kind: "violet", label: "Critique gate", role: "Five-axis rubric", reads: ["draft"], writes: ["critique"], lifecycle: "WORKING (judgment)", description: "Voice fidelity, canon consistency, pacing, character authenticity, prose quality. On fail: loop to Scribe with critique. Ceiling of 3 cycles." },
  continuity: { kind: "mint",   label: "Continuity editor", role: "Cross-book", reads: ["draft"], writes: ["continuity_notes"], lifecycle: "WORKING (review)", description: "Cross-references the canon graph across previous books. Catches series-level breakages a single-book Scribe can't." },
  polisher:   { kind: "mint",   label: "Prose polisher", role: "Line edit", reads: ["draft"], writes: ["polished"], lifecycle: "WORKING (refinement)", description: "Sentence-level rewrites for cadence and clarity. Doesn't change beats." },
  beta:       { kind: "mint",   label: "Beta reader", role: "Reader experience", reads: ["polished"], writes: ["reader_notes"], lifecycle: "WORKING (review)", description: "Approximates a first-time reader. Flags confusion, drag, surprise hits." },
};

window.NODE_LIBRARY = NODE_LIBRARY;

function NodeDetailDrawer({ open, nodeKey, onClose }) {
  const node = nodeKey ? NODE_LIBRARY[nodeKey] : null;
  return (
    <aside style={{
      position: "fixed",
      top: 0, right: 0,
      width: open ? 380 : 0,
      height: "100vh",
      background: WF_PALETTE.paper,
      borderLeft: open ? `1px solid ${WF_PALETTE.hairline}` : "none",
      boxShadow: open ? "-30px 0 60px rgba(14,14,26,0.35)" : "none",
      transition: "width 360ms cubic-bezier(0.22, 1, 0.36, 1)",
      overflow: "hidden",
      zIndex: 80,
    }}>
      {open && node && (
        <div style={{ width: 380, padding: "32px 28px", height: "100%", overflowY: "auto" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 18 }}>
            <div style={{
              fontFamily: "var(--font-mono)", fontSize: 10.5,
              letterSpacing: "0.14em", textTransform: "uppercase",
              color: WF_PALETTE.inkSoft,
            }}>· node · {node.role.toLowerCase()} ·</div>
            <button onClick={onClose} style={{
              background: "transparent", border: "none",
              fontSize: 18, color: WF_PALETTE.inkSoft,
              cursor: "pointer", padding: 4, lineHeight: 1,
            }}>×</button>
          </div>
          <svg width={120} height={48} style={{ marginBottom: 14 }}>
            <ArrowDefs />
            <Node kind={node.kind} label={node.label} x={0} y={6} w={120} h={36} status="live" />
          </svg>
          <h3 style={{
            fontFamily: "var(--font-display)", fontSize: 26, fontWeight: 500,
            letterSpacing: "-0.015em", color: WF_PALETTE.ink, margin: "8px 0 6px",
          }}>{node.label}</h3>
          <div style={{
            fontFamily: "var(--font-sans)", fontSize: 12,
            color: WF_PALETTE.inkSoft, marginBottom: 18,
          }}>{node.role}</div>
          <p style={{
            fontFamily: "var(--font-sans)", fontSize: 14, lineHeight: 1.6,
            color: WF_PALETTE.ink, margin: "0 0 24px",
          }}>{node.description}</p>

          <DetailRow label="Reads" items={node.reads} />
          <DetailRow label="Writes" items={node.writes} accent={WF_PALETTE.highlight} />
          <DetailRow label="Lifecycle position" raw={node.lifecycle} />

          <div style={{
            marginTop: 28, padding: "14px 16px",
            background: "#f6e8d8", borderRadius: 4,
            fontFamily: "var(--font-sans)", fontSize: 12.5, lineHeight: 1.55,
            color: WF_PALETTE.inkSoft,
          }}>
            <strong style={{ color: WF_PALETTE.ink }}>Trigger pattern.</strong>{" "}
            All input fields populated → daemon spawns with this node's subagent definition → work completes → output fields written → downstream re-evaluates.
          </div>

          <button onClick={onClose} style={{
            marginTop: 28, width: "100%",
            padding: "12px 16px",
            background: WF_PALETTE.ember, color: "#fff",
            border: "none", borderRadius: 4,
            fontFamily: "var(--font-sans)", fontSize: 13, fontWeight: 500,
            cursor: "pointer",
            letterSpacing: "0.02em",
          }}>Dismiss</button>
        </div>
      )}
    </aside>
  );
}

function DetailRow({ label, items, raw, accent }) {
  return (
    <div style={{ marginBottom: 14, paddingBottom: 12, borderBottom: `1px solid ${WF_PALETTE.hairlineSoft}` }}>
      <div style={{
        fontFamily: "var(--font-mono)", fontSize: 10,
        letterSpacing: "0.14em", textTransform: "uppercase",
        color: WF_PALETTE.inkSoft, marginBottom: 6, fontWeight: 600,
      }}>{label}</div>
      {raw ? (
        <div style={{ fontFamily: "var(--font-sans)", fontSize: 13, color: WF_PALETTE.ink }}>{raw}</div>
      ) : (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {items.map((it, i) => (
            <code key={i} style={{
              fontFamily: "var(--font-mono)", fontSize: 11,
              background: accent ? "rgba(233,69,96,0.12)" : "#efe4d0",
              color: accent || WF_PALETTE.ink,
              padding: "2px 7px", borderRadius: 3, border: "none",
            }}>{it}</code>
          ))}
        </div>
      )}
    </div>
  );
}

Object.assign(window, { NodeDetailDrawer, NODE_LIBRARY });
