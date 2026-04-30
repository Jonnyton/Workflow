// diagram-3-parallel.jsx — "Parallel execution zones" — 10-node team
// Shows where work happens concurrently with PARALLEL fan barriers.

function Diagram3_Parallel({ onNodeClick, selectedNode }) {
  const PH = WF_PALETTE;
  return (
    <PaperCard label="· parallel zones · 10-node team ·" style={{ padding: "44px 32px 28px" }}>
      <svg viewBox="0 0 560 920" width="100%" style={{ display: "block", maxWidth: 560, margin: "0 auto" }}>
        <ArrowDefs />

        {/* START */}
        <Node kind="ghost" label="START" x={215} y={20} w={130} />

        {/* LEAD */}
        <Node kind="indigo" label="lead" x={215} y={84} w={130} status="live"
              onClick={() => onNodeClick("lead")} selected={selectedNode === "lead"} />

        {/* DISCOVERY band */}
        <ExecutionBand x={36} y={172} w={488} h={84} label="parallel · fan-out" accent="#5b3624" />
        <Node kind="sage" label="researcher" x={70} y={196} w={130} h={48} status="live"
              onClick={() => onNodeClick("researcher")} selected={selectedNode === "researcher"} />
        <Node kind="sage" label="architect" x={360} y={196} w={130} h={48} status="live"
              onClick={() => onNodeClick("architect")} selected={selectedNode === "architect"} />

        {/* PLANNER barrier */}
        <Node kind="sage" label="planner" x={215} y={290} w={130} h={48}
              onClick={() => onNodeClick("planner")} selected={selectedNode === "planner"} />
        <text x={280} y={278} textAnchor="middle" fontFamily="var(--font-mono)" fontSize={9.5}
              fill={PH.inkSoft}>fan-in barrier</text>

        {/* IMPL band */}
        <ExecutionBand x={20} y={376} w={520} h={84} label="parallel · 3-way fan-out" accent="#5b3624" />
        <Node kind="sage" label="frontend_dev" x={50} y={400} w={130} h={48}
              onClick={() => onNodeClick("frontend_dev")} selected={selectedNode === "frontend_dev"} />
        <Node kind="sage" label="backend_dev" x={210} y={400} w={130} h={48}
              onClick={() => onNodeClick("backend_dev")} selected={selectedNode === "backend_dev"} />
        <Node kind="sage" label="db_dev" x={370} y={400} w={130} h={48}
              onClick={() => onNodeClick("db_dev")} selected={selectedNode === "db_dev"} />

        {/* QUALITY band */}
        <ExecutionBand x={36} y={494} w={488} h={84} label="parallel · quality (not redundant)" accent="#5b3624" />
        <Node kind="amber" label="tester" x={70} y={518} w={130} h={48}
              onClick={() => onNodeClick("tester")} selected={selectedNode === "tester"} />
        <Node kind="amber" label="reviewer" x={360} y={518} w={130} h={48}
              onClick={() => onNodeClick("reviewer")} selected={selectedNode === "reviewer"} />

        {/* CHECKER band */}
        <ExecutionBand x={88} y={612} w={384} h={66} label="fan-in" accent="#5b3624" />
        <Node kind="amber" label="checker" x={215} y={634} w={130} h={36}
              onClick={() => onNodeClick("checker")} selected={selectedNode === "checker"} />

        {/* gate */}
        <Diamond x={225} y={702} w={110} h={84} label="gate"
                 onClick={() => onNodeClick("gate")} selected={selectedNode === "gate"} />

        {/* docs */}
        <Node kind="violet" label="docs" x={215} y={808} w={130} h={48}
              onClick={() => onNodeClick("docs")} selected={selectedNode === "docs"} />

        {/* END */}
        <Node kind="ghost" label="END" x={215} y={874} w={130} />

        {/* Edges */}
        <Edge from={[280, 120]} to={[280, 172]} />
        <Edge from={[230, 196]} to={[135, 196]} curve={-30} />
        <Edge from={[330, 196]} to={[425, 196]} curve={30} />
        <Edge from={[135, 244]} to={[260, 290]} />
        <Edge from={[425, 244]} to={[300, 290]} />
        <Edge from={[280, 338]} to={[280, 376]} />
        <Edge from={[260, 400]} to={[115, 400]} curve={-30} />
        <Edge from={[300, 400]} to={[275, 400]} arrow={false} />
        <Edge from={[300, 400]} to={[435, 400]} curve={30} />
        <Edge from={[115, 448]} to={[135, 518]} />
        <Edge from={[275, 448]} to={[280, 612]} />
        <Edge from={[435, 448]} to={[425, 518]} />
        <Edge from={[135, 566]} to={[260, 634]} />
        <Edge from={[425, 566]} to={[300, 634]} />
        <Edge from={[280, 670]} to={[280, 702]} />
        <Edge from={[280, 786]} to={[280, 808]} dashed label="PASS" />
        <Edge from={[280, 856]} to={[280, 874]} />
      </svg>
      <DiagCaption>
        <strong style={{ color: PH.ink }}>Fan-in barriers.</strong> <InlineCode>planner</InlineCode> waits for both{" "}
        <InlineCode kind="sage">researcher</InlineCode> and <InlineCode kind="sage">architect</InlineCode> to finish before its
        daemon spawns — the trigger is "all three of my input fields populated," not "any one of them." Same for{" "}
        <InlineCode kind="amber">tester</InlineCode> (waits for all three * _dev) and <InlineCode kind="amber">checker</InlineCode>{" "}
        (waits for both tester and reviewer).
      </DiagCaption>
    </PaperCard>
  );
}

window.Diagram3_Parallel = Diagram3_Parallel;
