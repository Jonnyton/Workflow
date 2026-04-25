# User-Chat Intelligence Report — 2026-04-24: Competitor Trials Sweep

**Sessions read:** `user_sim_session.md` (2026-04-23 19:16 entries), `maya_okafor/competitor_trials.md`, `priya_ramaswamy/competitor_trials.md`, `priya_ramaswamy/sessions.md`, `priya_ramaswamy/grievances.md`, `priya_ramaswamy/wins.md`

**Prior report:** `2026-04-23-pre-dispatch-sweep.md` — signals below are NEW, not in prior report.

---

## What user-sim did

**2026-04-23 session (offline):**
1. Priya Session 2 mock — reviewer-2 round-2 ask: add BIOCLIM + RF alongside MaxEnt sweep.
2. Maya n8n competitor trial — friend Diane brunch rec → bounced at Docker install step.
3. Priya W&B Sweeps competitor trial — PhD student next desk rec → actually ran the sweep (4h setup), lost on handoff.

---

## New product signals

### Signal 1 — Second-chat trap (workspace-memory continuity)
**Source:** Priya Session 2 mock + user_sim_session.md signal #1.

Distinct from first-chat disambiguation. Priya Session 2: chatbot must find + extend a prior sweep run WITHOUT re-scaffolding blank-slate. If it asks "what were you working on?" instead of calling `list_runs` → she loses faith in workspace memory → retention failure at session 2.

**Chain-break:** Interface 1 — chatbot orientation gap. No existing `control_station` rule covers "re-anchor to prior run before answering a follow-on question." Prior audit proposed a `list_runs + get_run_output` behavioral rule; this signal confirms it's load-bearing for retention, not just UX.

**Proposed action:** Add `control_station` prompt rule: "When user's message references a prior run, sweep, or analysis without naming it explicitly, call `list_runs` to re-anchor before responding. Never assert from memory what runs exist."

---

### Signal 2 — Extension-as-first-class-primitive gap
**Source:** Priya Session 2 mock + user_sim_session.md signal #6.

"Add BIOCLIM + RF for comparison on the same 14 species" has no clean Workflow verb. "New branch" implies fresh scaffolding. "New run" implies same branch. The chatbot would have to semantically infer "extend this completed branch with additional algorithm nodes." Neither existing primitive surfaces this as a first-class intent.

**Chain-break:** Interface 1 — primitive gap. The chatbot is left to improvise where it should have a clear tool.

**Assessment:** This is a real primitive gap, but scoping it is non-trivial (clone-branch-and-add-nodes vs. re-run-with-additional-params vs. new sibling branch). Recommend adding to ideas/PIPELINE.md as a scoping candidate rather than dispatching immediately. NOT the same as the `control_station` re-anchor rule (Signal 1) — that's behavioral; this is structural.

---

### Signal 3 — W&B Sweeps: CV-as-first-class-primitive is a structural moat
**Source:** `priya_ramaswamy/competitor_trials.md` W&B trial.

W&B Sweeps actually runs sweeps, scales, and gives Priya a dashboard. The Cursor "gives you code not the result" critique does NOT apply. W&B is a real competitor for Priya in raw orchestration capability.

**W&B loses on:** (a) CV is user's problem — she spent 90 min getting CV inside a W&B "run" right; (b) reproducibility artifact = W&B dashboard link, not a local repro script reviewer can run; (c) peer-review community: ecology reviewers won't create W&B accounts.

**Moat:** CV-as-first-class-primitive on evaluator nodes (spatial CV, stratified CV, block CV as a parameter, not user-implemented) is something W&B can't match without a product re-architecture. This is the one structural advantage that survives W&B's orchestration capability.

**Proposed action:** Promote "CV-as-first-class-primitive on evaluator nodes" to a scoping candidate. Not blocked on anything; could be a `node_def` extension spec.

---

### Signal 4 — Hyperparameter-importance evaluator: cheap W&B parity win
**Source:** `priya_ramaswamy/competitor_trials.md` W&B trial.

W&B's one substantive win Priya would actually want: hyperparameter importance analysis (which knobs matter most across the sweep). W&B computes this automatically. Workflow has no equivalent.

**Assessment:** This is a domain-specific evaluator node (scientific/ML domain), not an engine primitive. User-sim estimates it as "cheap to add, high-value for scientific users." Worth adding as a `hyperparameter_importance` evaluator node in the science domain. Doesn't block anything current.

**Proposed action:** Capture in ideas/INBOX.md as a domain-skill candidate for the scientific-computing module.

---

### Signal 5 — Peer-review artifact is the positioning frame vs. W&B
**Source:** `priya_ramaswamy/competitor_trials.md` W&B trial.

Sharpest head-to-head: **W&B = "here is your sweep dashboard, log in to see it." Workflow = "here is your CSV, repro script, and methods paragraph — paste into your paper."** The audience distinction: W&B speaks to ML teams; Workflow speaks to Priya's reviewers.

**Implication for copy/landing page:** "The output is what the reviewer runs" is the one-line pitch for scientific-computing tier-2 users. Not discoverable from first-principles.

---

### Signal 6 — n8n positioning: "zero build step" is the only frame that wins
**Source:** `maya_okafor/competitor_trials.md` n8n trial.

n8n wins on: 400+ integrations, determinism, self-hosted privacy, one-time-build-runs-forever. Workflow cannot win a side-by-side feature grid on integration count.

**Killer line from Maya:** "I don't have an IT guy. My IT is me and Claude." This is the Tier-1 user summary. Worth capture in landing copy or trial testimonials.

**The only winning frame:** "zero build step." Maya goes from "I have this problem" to "here's a CSV I can import" in one conversation, zero canvas-building. n8n can't play in this category.

**Risk noted:** if Workflow tier-2 daemon install is >30 min, Diane's IT-guy-hosted n8n wins on perceived simplicity. Tray install friction is a retention risk vs. n8n.

---

## Plans proposed

| Type | Plan | Disposition |
|---|---|---|
| `control_station` prompt | Add rule: re-anchor to prior runs via `list_runs` before responding to session-follow-on asks | Low-stakes; navigator can draft + lead approves |
| Ideas capture | "Extend run / continue branch" primitive scoping | Capture in `ideas/PIPELINE.md` |
| Ideas capture | CV-as-first-class-primitive on evaluator nodes | Capture in `ideas/PIPELINE.md` |
| Ideas capture | `hyperparameter_importance` domain evaluator node (science module) | Capture in `ideas/INBOX.md` |
| Copy/marketing | "The output is what the reviewer runs" (Priya positioning vs W&B) | Durable finding; no dispatch needed |
| Copy/marketing | "I don't have an IT guy. My IT is me and Claude." (Maya vs n8n) | Durable finding; no dispatch needed |

---

## No dispatch needed this cycle

All signals are (a) ideas candidates, (b) a low-stakes `control_station` prompt edit (navigator can own), or (c) positioning intelligence with no immediate code implication. No dev tasks generated from this sweep.

The `control_station` prompt edit (Signal 1 re-anchor rule) is the only behavioral fix with urgency — Devin M27 and Priya M2 both hit this path. Navigator will draft and notify lead.
