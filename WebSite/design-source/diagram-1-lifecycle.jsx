// diagram-1-lifecycle.jsx — "What happens inside a single node"
// Recreates the lifecycle diagram (IDLE → TRIGGERED → DAEMON_SPAWN → WORKING → WRITING_HANDOFF → FAN_OUT)
// with parchment annotations on the side.

function Diagram1_Lifecycle({ animatePhase, onNodeClick }) {
  // animatePhase: 0..5 indicates which lifecycle stage is currently glowing
  const PH = WF_PALETTE;
  const phases = ["IDLE", "TRIGGERED", "DAEMON_SPAWN", "WORKING", "WRITING_HANDOFF", "FAN_OUT"];
  const isActive = (i) => animatePhase === i;

  return (
    <PaperCard label="· lifecycle · single node ·" style={{ padding: "44px 32px 28px" }}>
      <svg viewBox="0 0 540 620" width="100%" style={{ display: "block", maxWidth: 540, margin: "0 auto" }}>
        <ArrowDefs />

        {/* IDLE — top right */}
        <Annotation x={295} y={18} w={160} lines={["node registered"]} />
        <Node kind={isActive(0) ? "ember" : "cream"} label="IDLE" x={310} y={62} w={130} status="idle" />

        {/* Inbound trigger annotation */}
        <Annotation x={120} y={120} w={170} lines={["Inbound edge fires", "(upstream wrote my", "input field)"]} />

        {/* TRIGGERED */}
        <Node kind={isActive(1) ? "ember" : "cream"} label="TRIGGERED" x={310} y={188} w={130} />

        {/* zero compute annotation */}
        <Annotation x={20} y={180} w={140} lines={["zero compute,", "zero tokens"]} />

        {/* outer runner annotation */}
        <Annotation x={130} y={244} w={170} lines={["outer runner notices"]} />

        {/* no inbound trigger */}
        <Annotation x={460} y={188} w={70} lines={["no inbound", "trigger", "(quiet)"]} />

        {/* DAEMON_SPAWN */}
        <Node kind={isActive(2) ? "ember" : "cream"} label="DAEMON_SPAWN" x={310} y={290} w={130} />

        {/* Claude Code session annotation */}
        <Annotation x={100} y={296} w={200} lines={["Claude Code session", "inherits subagent", "definition", "+ input state fields"]} />

        {/* WORKING */}
        <Node kind={isActive(3) ? "sage" : "cream"} label="WORKING" x={310} y={388} w={130} onClick={() => onNodeClick && onNodeClick("dev")} />

        {/* tokens annotation */}
        <Annotation x={20} y={388} w={150} lines={["only state where", "tokens are spent"]} />

        {/* produces output annotation */}
        <Annotation x={170} y={428} w={170} lines={["produces output", "per output_keys", "contract"]} />

        {/* WRITING_HANDOFF */}
        <Node kind={isActive(4) ? "ember" : "cream"} label="WRITING_HANDOFF" x={310} y={490} w={150} />

        {/* writes state annotation */}
        <Annotation x={170} y={500} w={140} lines={["writes state", "signals downstream", "edges"]} />

        {/* FAN_OUT */}
        <Node kind={isActive(5) ? "ember" : "cream"} label="FAN_OUT" x={335} y={562} w={120} />

        {/* session exits */}
        <Annotation x={460} y={400} w={75} lines={["session exits", "node returns", "to rest"]} />

        {/* Edges */}
        <Edge from={[375, 98]} to={[375, 188]} />
        <Edge from={[375, 224]} to={[375, 290]} />
        <Edge from={[375, 326]} to={[375, 388]} />
        <Edge from={[375, 424]} to={[375, 490]} />
        <Edge from={[385, 526]} to={[395, 562]} />

        {/* Loop back idle */}
        <path d="M 460 580 Q 510 400 460 88" fill="none" stroke={PH.creamStroke}
              strokeWidth={1.25} strokeDasharray="5 4" markerEnd="url(#wf-arrow)" opacity={0.6} />
      </svg>
      <DiagCaption>
        <strong style={{ color: PH.ink }}>Two things to notice:</strong> compute is only spent in <InlineCode kind="sage">WORKING</InlineCode>{" "}
        (the rest of the lifecycle is bookkeeping), and <InlineCode>IDLE</InlineCode> is the default state — a team of 20 with only 3 active nodes
        is burning tokens for 3, not 20.
      </DiagCaption>
    </PaperCard>
  );
}

window.Diagram1_Lifecycle = Diagram1_Lifecycle;
