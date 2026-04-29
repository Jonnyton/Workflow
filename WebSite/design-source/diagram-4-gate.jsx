// diagram-4-gate.jsx — "Gate routing — the failure-class matrix"
// Resolution doubles with each tier. Shows a single gate fanning out to many recovery routes.

function Diagram4_GateRouting({ tier, onNodeClick }) {
  // tier: '3' | '5' | '10'
  const data = {
    "3":  { gateLabel: "3-node gate", classes: [
      ["PASS", "END", "green"],
      ["FAIL_PLAN", "planner", "sage"],
      ["FAIL_IMPL", "dev", "sage"],
      ["FAIL_TEST", "tester", "amber"],
      ["FAIL_UNCLEAR", "lead", "indigo"],
    ]},
    "5":  { gateLabel: "5-node gate", classes: [
      ["PASS", "END", "green"],
      ["FAIL_IMPL", "dev", "sage"],
      ["FAIL_PLAN", "planner", "sage"],
      ["FAIL_TEST", "tester", "amber"],
      ["FAIL_UNCLEAR", "lead", "indigo"],
    ]},
    "10": { gateLabel: "10-node gate", classes: [
      ["PASS", "END", "green"],
      ["FAIL_RESEARCH", "researcher", "sage"],
      ["FAIL_ARCH", "architect", "sage"],
      ["FAIL_PLAN", "planner", "sage"],
      ["FAIL_IMPL_FE", "frontend_dev", "sage"],
      ["FAIL_IMPL_BE", "backend_dev", "sage"],
      ["FAIL_IMPL_DB", "db_dev", "sage"],
      ["FAIL_REVIEW", "reviewer", "amber"],
      ["FAIL_UNCLEAR", "lead", "indigo"],
    ]},
  };
  const d = data[tier] || data["10"];
  const rows = d.classes.length;
  const rowH = 50;
  const totalH = rows * rowH + 60;

  return (
    <PaperCard label={`· gate routing · resolution = ${rows} classes ·`} style={{ padding: "44px 32px 28px" }}>
      <svg viewBox={`0 0 560 ${totalH}`} width="100%" style={{ display: "block", maxWidth: 560, margin: "0 auto" }}>
        <ArrowDefs />
        <Node kind="cream" label="check_result" x={20} y={totalH/2 - 18} w={130} h={36} />
        <Diamond x={195} y={totalH/2 - 50} w={120} h={100} label={d.gateLabel} kind="ember" />
        {d.classes.map(([cls, dest, kind], i) => {
          const y = 30 + i * rowH;
          const isPass = cls === "PASS";
          return (
            <g key={i}>
              <Node kind="ghost" label={cls} x={350} y={y} w={100} h={32} />
              <Node kind={kind} label={dest} x={470} y={y} w={70} h={32}
                    onClick={() => onNodeClick(dest)} />
              <path d={`M 315 ${totalH/2} Q 360 ${y + 16} 350 ${y + 16}`}
                    fill="none" stroke={WF_PALETTE.creamStroke}
                    strokeWidth={1} markerEnd="url(#wf-arrow)"
                    strokeDasharray={isPass ? undefined : undefined} />
              <Edge from={[450, y + 16]} to={[470, y + 16]} />
            </g>
          );
        })}
      </svg>
      <DiagCaption>
        <strong style={{ color: WF_PALETTE.ink }}>Resolution doubles with each tier.</strong> 3-node = 4 classes, 5-node = 5 classes,
        10-node = 9 classes, 20-node = 18 classes. Higher resolution = more precise retry routing = fewer wasted iterations.
      </DiagCaption>
    </PaperCard>
  );
}

window.Diagram4_GateRouting = Diagram4_GateRouting;
