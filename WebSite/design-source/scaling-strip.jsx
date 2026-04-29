// scaling-strip.jsx — "How the four variants scale side-by-side"
// Tiny horizontal strips showing 3/5/10/20 node teams as miniature timelines.

function ScalingStrip({ onNodeClick, selectedTier, onTierSelect }) {
  const tiers = [
    { n: 3,  nodes: [["lead","indigo"], ["dev","sage"], ["checker","amber"], ["gate","ember"]] },
    { n: 5,  nodes: [["lead","indigo"], ["researcher","sage"], ["dev","sage"], ["tester","amber"], ["checker","amber"], ["gate","ember"]] },
    { n: 10, nodes: [["lead","indigo"], ["researcher","sage"], ["architect","sage"], ["planner","sage"], ["frontend_dev","sage"], ["backend_dev","sage"], ["db_dev","sage"], ["tester","amber"], ["reviewer","amber"], ["checker","amber"], ["gate","ember"], ["docs","violet"]] },
    { n: 20, nodes: [["lead","indigo"], ["researcher","sage"], ["architect","sage"], ["api_designer","sage"], ["planner","sage"], ["risk","sage"], ["frontend_dev","sage"], ["backend_dev","sage"], ["db_dev","sage"], ["mig","sage"], ["mob","sage"], ["unit_t","amber"], ["integ_t","amber"], ["e2e_t","amber"], ["code_rev","amber"], ["sec_rev","amber"], ["perf_rev","amber"], ["debugger","amber"], ["checker","amber"], ["gate","ember"], ["docs","violet"], ["deploy","violet"]] },
  ];
  return (
    <PaperCard label="· four variants · same flow, different resolution ·" style={{ padding: "44px 28px 28px" }}>
      {tiers.map(t => (
        <div key={t.n}
             onClick={() => onTierSelect && onTierSelect(t.n)}
             style={{
               display: "flex", alignItems: "center", gap: 14, marginBottom: 10,
               cursor: "pointer", padding: "10px 8px", borderRadius: 4,
               background: selectedTier === t.n ? "rgba(233,69,96,0.08)" : "transparent",
               transition: "background 200ms",
             }}>
          <div style={{
            fontFamily: "var(--font-mono)", fontSize: 12,
            color: selectedTier === t.n ? WF_PALETTE.highlight : WF_PALETTE.ink,
            width: 60, fontWeight: 600,
          }}>{t.n}-node</div>
          <div style={{
            flex: 1,
            background: WF_PALETTE.band,
            borderRadius: 4, padding: "6px 8px",
            display: "flex", gap: 4, flexWrap: "nowrap", overflowX: "auto",
          }}>
            {t.nodes.map(([n, k], i) => (
              <div key={i} style={{
                background: NODE_STYLES[k].fill,
                color: NODE_STYLES[k].ink,
                fontSize: 9.5, fontFamily: "var(--font-sans)",
                padding: "3px 6px", borderRadius: 2, whiteSpace: "nowrap",
                border: `1px solid ${NODE_STYLES[k].stroke}`,
              }}>{n}</div>
            ))}
          </div>
        </div>
      ))}
      <DiagCaption style={{ marginTop: 18 }}>
        Same flow, three resolutions of specialization. The scaling rule: each tier splits the band most likely to be the bottleneck.
        <strong style={{color: WF_PALETTE.ink}}> 3 → 5</strong>: splits the monolithic dev role into plan + implement + test.{" "}
        <strong style={{color: WF_PALETTE.ink}}>5 → 10</strong>: parallelizes discovery (researcher + architect) and implementation
        (3× *_dev). <strong style={{color: WF_PALETTE.ink}}>10 → 20</strong>: splits review on security/perf axes, splits testing into unit/integ/e2e layers, adds delivery pipeline.
      </DiagCaption>
    </PaperCard>
  );
}

window.ScalingStrip = ScalingStrip;
