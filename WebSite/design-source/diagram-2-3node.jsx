// diagram-2-3node.jsx — "3-node, fully annotated"
// The lead → dev → checker → gate loop with every trigger, state field, and decision visible.

function Diagram2_ThreeNode({ onNodeClick, selectedNode, focusFlow }) {
  // focusFlow: 0 = none, 1 = solid (forward), 2 = dashed (loop-back)
  const dimSolid = focusFlow === 2;
  const dimDashed = focusFlow === 1;

  return (
    <PaperCard label="· 3-node, fully annotated ·" style={{ padding: "44px 32px 28px" }}>
      <svg viewBox="0 0 540 780" width="100%" style={{ display: "block", maxWidth: 540, margin: "0 auto" }}>
        <ArrowDefs />

        {/* START */}
        <Node kind="cream" label={["START:", "project_brief", "acceptance_criteria", "retry_budget"]}
              x={195} y={20} w={150} h={70} multiline />
        <Annotation x={205} y={104} w={130} lines={["initial state", "written"]} />

        {/* LEAD */}
        <Node kind="indigo" label="lead" x={205} y={150} w={130} h={56} sub="writes: task_list, current_task"
              onClick={() => onNodeClick("lead")} status="live" selected={selectedNode === "lead"} />

        {/* trigger annot */}
        <Annotation x={50} y={232} w={170} lines={["trigger: current_task", "written", "dev daemon spawns"]} />

        {/* DEV */}
        <Node kind="sage" label="dev" x={50} y={310} w={130} h={56} sub="reads: current_task / writes: implementation"
              onClick={() => onNodeClick("dev")} status="live" selected={selectedNode === "dev"} />

        {/* trigger 2 */}
        <Annotation x={50} y={386} w={170} lines={["trigger: implementation", "written", "checker daemon spawns"]} />

        {/* loop-back annotation */}
        <Annotation x={350} y={310} w={160} lines={["gate_decision =", "'LOOP_TO: lead'", "outer runner re-", "invokes", "retry_count++"]} />

        {/* retry budget annot */}
        <Annotation x={350} y={420} w={160} lines={["retry_budget", "exhausted", "→ SOFT_ESCALATE", "decompose + reset"]} />

        {/* CHECKER */}
        <Node kind="amber" label="checker" x={50} y={470} w={130} h={56} sub="reads: implementation + criteria / writes: check_result"
              onClick={() => onNodeClick("checker")} status="idle" selected={selectedNode === "checker"} />

        <Annotation x={50} y={546} w={170} lines={["trigger: check_result", "written", "gate daemon spawns"]} />

        {/* GATE diamond */}
        <Diamond x={205} y={616} w={130} h={84} label="gate"
                 onClick={() => onNodeClick("gate")} selected={selectedNode === "gate"} />

        {/* gate decision */}
        <Node kind="cream" label={["gate_decision =", "'END'", "✓ PASS"]} x={205} y={714} w={130} h={48} multiline />

        {/* END */}
        <Node kind="ghost" label={["END:", "deliverable"]} x={215} y={774} w={110} h={36} multiline />

        {/* Edges — solid = state-write, dashed = outer-runner */}
        <g opacity={dimSolid ? 0.25 : 1}>
          <Edge from={[270, 90]} to={[270, 150]} />
          <Edge from={[230, 206]} to={[120, 310]} />
          <Edge from={[120, 366]} to={[120, 470]} />
          <Edge from={[180, 498]} to={[225, 616]} curve={20} />
          <Edge from={[270, 700]} to={[270, 714]} />
          <Edge from={[270, 762]} to={[270, 774]} />
        </g>

        {/* Dashed loop-back */}
        <g opacity={dimDashed ? 0.25 : 1}>
          <path d="M 320 658 Q 470 500 380 220 Q 360 180 335 178"
                fill="none" stroke={WF_PALETTE.creamStroke} strokeWidth={1.25}
                strokeDasharray="5 4" markerEnd="url(#wf-arrow)" />
        </g>
      </svg>
      <DiagCaption>
        <strong style={{ color: WF_PALETTE.ink }}>Solid arrows</strong> = happens automatically via state-write trigger.{" "}
        <strong style={{ color: WF_PALETTE.ink }}>Dashed arrows</strong> = happens via the outer runner interpreting{" "}
        <InlineCode>gate_decision</InlineCode> on the next <InlineCode>run_branch</InlineCode> call.
      </DiagCaption>
      <DiagCaption style={{ marginTop: 10 }}>
        This distinction matters: the forward path is pure data-flow; the loop-back requires an orchestrator one level up.
      </DiagCaption>
    </PaperCard>
  );
}

window.Diagram2_ThreeNode = Diagram2_ThreeNode;
