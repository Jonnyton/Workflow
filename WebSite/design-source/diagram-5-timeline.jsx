// diagram-5-timeline.jsx — Gantt-style execution timeline (10-node)
// Vertical bars show what's active simultaneously. Bands = phases, blocks = active node windows.

function Diagram5_Timeline() {
  const PH = WF_PALETTE;
  // Each row: phase label, list of {node, start, end, kind}
  const rows = [
    { label: "Coordinator",   items: [["lead", 0, 8, "indigo"]] },
    { label: "Discovery",     items: [["researcher", 8, 20, "sage"], ["architect", 8, 27, "sage"]] },
    { label: "Planning",      items: [["planner", 27, 33, "sage"]] },
    { label: "Implementation",items: [["frontend_dev", 33, 51, "sage"], ["backend_dev", 33, 58, "sage"], ["db_dev", 33, 47, "sage"]] },
    { label: "Quality",       items: [["tester", 58, 73, "amber"], ["reviewer", 58, 71, "amber"]] },
    { label: "Finalize",      items: [["checker", 73, 81, "amber"], ["gate", 81, 84, "ember"], ["docs", 84, 92, "violet"]] },
  ];
  const W = 540, scale = 5.4, padL = 100, rowH = 38;
  return (
    <PaperCard label="· execution timeline · who's working when ·" style={{ padding: "44px 28px 28px" }}>
      <svg viewBox={`0 0 ${W} ${rows.length * rowH + 56}`} width="100%" style={{ display: "block" }}>
        <ArrowDefs />
        {/* Time axis */}
        {[0, 15, 30, 45, 60, 75, 90].map(t => (
          <g key={t}>
            <line x1={padL + t * scale} x2={padL + t * scale} y1={20} y2={rows.length * rowH + 30}
                  stroke={PH.hairlineSoft} strokeWidth={0.75} strokeDasharray="2 3" />
            <text x={padL + t * scale} y={rows.length * rowH + 48} textAnchor="middle"
                  fontFamily="var(--font-mono)" fontSize={9.5} fill={PH.inkSoft}>{t}</text>
          </g>
        ))}
        {rows.map((row, i) => {
          const y = 20 + i * rowH;
          return (
            <g key={i}>
              <rect x={padL} y={y} width={W - padL - 12} height={rowH - 6}
                    fill={PH.band} fillOpacity={0.22} />
              <text x={8} y={y + rowH/2 + 2} fontFamily="var(--font-sans)"
                    fontSize={11.5} fill={PH.ink} fontWeight={500}>{row.label}</text>
              {row.items.map(([n, s, e, k], j) => (
                <g key={j} transform={`translate(${padL + s * scale}, ${y + 4})`}>
                  <rect width={(e - s) * scale} height={rowH - 14} rx={2}
                        fill={NODE_STYLES[k].fill} stroke={NODE_STYLES[k].stroke} strokeWidth={0.75} />
                  <text x={(e - s) * scale / 2} y={(rowH - 14) / 2 + 4} textAnchor="middle"
                        fontFamily="var(--font-sans)" fontSize={10}
                        fill={NODE_STYLES[k].ink} fontWeight={500}>{n}</text>
                </g>
              ))}
            </g>
          );
        })}
      </svg>
      <DiagCaption>
        Vertical bars show what's running simultaneously. Discovery overlaps; <InlineCode kind="sage">researcher</InlineCode>{" "}
        finishes faster than <InlineCode kind="sage">architect</InlineCode> but the <InlineCode kind="sage">planner</InlineCode>{" "}
        waits for both. The Implementation band runs three nodes in parallel —{" "}
        <InlineCode>max(fe, be, db)</InlineCode> = 25s instead of <InlineCode>fe + be + db</InlineCode> = 60s.
        Parallelism shaves <strong style={{ color: PH.ink }}>~60% off wall-clock</strong> — token cost is unchanged, since each daemon runs independently, but time-to-result drops dramatically.
      </DiagCaption>
    </PaperCard>
  );
}

window.Diagram5_Timeline = Diagram5_Timeline;
