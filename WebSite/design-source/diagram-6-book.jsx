// diagram-6-book.jsx — Book-publishing pipeline (Plan→Draft→Integrate→Produce→Publish)
// + Scribe critique-loop + canon retrieval

function Diagram6_BookPipeline({ onNodeClick, selectedNode }) {
  return (
    <PaperCard label="· book pipeline · five phases ·" style={{ padding: "44px 28px 28px" }}>
      <svg viewBox="0 0 560 200" width="100%" style={{ display: "block", maxWidth: 560, margin: "0 auto" }}>
        <ArrowDefs />
        {[
          ["Plan", "outline", "violet", 10],
          ["Draft", "scene loop", "violet", 120],
          ["Integrate", "assemble", "violet", 230],
          ["Produce", "format", "mint", 340],
          ["Publish", "distribute", "mint", 450],
        ].map(([t, sub, kind, x], i, arr) => (
          <g key={i}>
            <Node kind={kind} label={t} sub={sub} x={x} y={40} w={100} h={60}
                  onClick={() => onNodeClick && onNodeClick(t.toLowerCase())} />
            {i < arr.length - 1 && (
              <Edge from={[x + 100, 70]} to={[x + 110, 70]} />
            )}
          </g>
        ))}
        <text x={280} y={150} textAnchor="middle" fontFamily="var(--font-sans)" fontSize={12}
              fontStyle="italic" fill={WF_PALETTE.inkSoft}>
          ↻ reader signal and reviews feed back into Plan for book N+1
        </text>
      </svg>
      <DiagCaption>
        Plan and Draft are where the interesting work happens. The Draft phase is a <strong style={{color: WF_PALETTE.ink}}>cycle, not a step</strong>{" "}
        — every scene runs through critique-and-revise before it integrates.
      </DiagCaption>
    </PaperCard>
  );
}

function Diagram7_DraftLoop({ onNodeClick, selectedNode, animateLoop }) {
  return (
    <PaperCard label="· draft phase · critique loop ·" style={{ padding: "44px 28px 28px" }}>
      <svg viewBox="0 0 560 460" width="100%" style={{ display: "block", maxWidth: 560, margin: "0 auto" }}>
        <ArrowDefs />
        <Node kind="ghost" label={["Assemble prompt", "canon context + scene plan + prior state"]} multiline
              x={170} y={20} w={220} h={56} />
        <Node kind="violet" label={["Scribe drafts scene", "initial prose"]} multiline
              x={170} y={110} w={220} h={56}
              onClick={() => onNodeClick("scribe")} selected={selectedNode === "scribe"}
              status={animateLoop ? "live" : null} />
        <Node kind="violet" label={["Critique gate", "voice, canon, pacing, character, prose"]} multiline
              x={170} y={210} w={220} h={56}
              onClick={() => onNodeClick("critique")} selected={selectedNode === "critique"} />
        <Node kind="violet" label={["Continuity check", "canon cross-reference across books"]} multiline
              x={170} y={310} w={220} h={56}
              onClick={() => onNodeClick("continuity")} selected={selectedNode === "continuity"} />
        <Node kind="ghost" label={["Commit to chapter worktree", "update status.md and plan.md"]} multiline
              x={170} y={400} w={220} h={50} />

        <Edge from={[280, 76]} to={[280, 110]} />
        <Edge from={[280, 166]} to={[280, 210]} />
        <Edge from={[280, 266]} to={[280, 310]} label="pass" labelOffset={20} />
        <Edge from={[280, 366]} to={[280, 400]} />

        {/* Loop back fail */}
        <path d="M 170 250 Q 80 250 80 140 Q 80 130 170 138"
              fill="none" stroke={WF_PALETTE.creamStroke} strokeWidth={1.25}
              strokeDasharray="5 4" markerEnd="url(#wf-arrow)"
              opacity={animateLoop ? 1 : 0.7} />
        <text x={50} y={195} fontFamily="var(--font-sans)" fontSize={11}
              fontStyle="italic" fill={WF_PALETTE.inkSoft}>fail</text>
        <text x={50} y={210} fontFamily="var(--font-sans)" fontSize={11}
              fontStyle="italic" fill={WF_PALETTE.inkSoft}>+ critique</text>
      </svg>
      <DiagCaption>
        The critique gate runs the Scribe's own output against a five-axis rubric — voice fidelity, canon consistency, pacing,
        character authenticity, prose quality. On fail, the draft loops back with the critique appended as context — not discarded —
        so the next pass targets the specific weaknesses. <strong style={{color: WF_PALETTE.ink}}>Ceiling of N=3</strong> revision
        cycles prevents runaway loops.
      </DiagCaption>
    </PaperCard>
  );
}

function Diagram8_CanonRetrieval({ onNodeClick }) {
  return (
    <PaperCard label="· canon retrieval · agentic router ·" style={{ padding: "44px 28px 28px" }}>
      <svg viewBox="0 0 560 440" width="100%" style={{ display: "block", maxWidth: 560, margin: "0 auto" }}>
        <ArrowDefs />
        <Node kind="ghost" label={["Canon query", "from Scribe or Architect"]} multiline x={200} y={20} w={160} h={50} />
        <Node kind="violet" label={["Agentic router", "classifies query intent"]} multiline x={200} y={100} w={160} h={50} />
        <Node kind="mint" label={["GraphRAG", "factions, relationships"]} multiline x={20} y={190} w={160} h={56}
              onClick={() => onNodeClick && onNodeClick("graphrag")} />
        <Node kind="mint" label={["Vector search", "vibe, similar scenes"]} multiline x={200} y={190} w={160} h={56}
              onClick={() => onNodeClick && onNodeClick("vector")} />
        <Node kind="mint" label={["Direct lookup", "named passages"]} multiline x={380} y={190} w={160} h={56}
              onClick={() => onNodeClick && onNodeClick("direct")} />
        <Node kind="violet" label={["Synthesizer", "merge, rerank, cite sources"]} multiline x={200} y={290} w={160} h={50} />
        <Node kind="ghost" label={["Canon context", "prompt-ready with citations"]} multiline x={200} y={370} w={160} h={50} />

        <Edge from={[280, 70]} to={[280, 100]} />
        <Edge from={[245, 150]} to={[100, 190]} />
        <Edge from={[280, 150]} to={[280, 190]} />
        <Edge from={[315, 150]} to={[460, 190]} />
        <Edge from={[100, 246]} to={[245, 290]} />
        <Edge from={[280, 246]} to={[280, 290]} />
        <Edge from={[460, 246]} to={[315, 290]} />
        <Edge from={[280, 340]} to={[280, 370]} />
      </svg>
      <DiagCaption>
        The router classifies on intent. Multi-hop entity queries → GraphRAG. Vibe matches → Vector. Named passages → Direct lookup.
        The synthesizer merges, reranks, and emits a prompt-ready excerpt with citations back to source passages.
      </DiagCaption>
    </PaperCard>
  );
}

Object.assign(window, { Diagram6_BookPipeline, Diagram7_DraftLoop, Diagram8_CanonRetrieval });
