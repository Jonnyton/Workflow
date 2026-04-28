---
title: The deploy pipe is the real chain-break
date: 2026-04-20
author: navigator
status: shipped
shipped_date: 2026-04-20
shipped_in: deploy-prod.yml § "Verify secrets present" (L81-89) + "Open deploy-failed issue" (L246+); fix-1 (deploy-failure GH-Issue alarm) live
status_detail: fix-1 shipped (deploy-failed alarm with secrets verification); fixes 2-5 each have separate downstream notes/tasks
---

# The deploy pipe is the real chain-break

Today we landed six "fixes" in commits 7848f19, df197a3, 45e9d0d + Task #6/#16/#20. **None reached production.** All three `deploy-prod` runs failed at "Verify secrets present" because `HETZNER_HOST` / `HETZNER_SSH_USER` / `HETZNER_SSH_KEY` were never configured in GitHub Actions. The droplet is running old pre-cluster code. We noticed 30+ min later only by diffing error strings.

Every bug we triaged today — changes_json mangle, WIKI_PATH leak, get_status caveats, wiki scrub, scaffold seed, NER stopwords — was a real chain-break fix. But ceremonial if deploy-pipe is severed. The load-bearing chain-break sits *upstream* of all of them.

## 3-layer lens

- **System.** Deploy pipeline returns green (workflow ran) but ships nothing. No alarm on secret-missing. No drift-check between intended env vs live env.
- **Chatbot.** `get_status` cannot ground "is the fix live?" — no git SHA, no image tag, no deploy timestamp. Tier-1 chatbots literally cannot answer "did your fix land?"
- **User.** Trust collapses silently. Host pushes, host assumes landed, next probe fails the same way, host tries to diagnose a "fixed" bug that's actually still the same bug.

**Load-bearing question:** *Does this make the user's chatbot better at serving the user's real goals?* When the deploy pipe lies, every downstream answer the chatbot gives is stale. This is the biggest single leverage point on the board right now.

## Structural fixes, ranked by leverage

1. **Deploy-failure alarm (GH-Issue sink, forever-rule shape).** `deploy-prod.yml` already opens issues on canary red (Row H pattern); extend to ANY deploy-job failure including "secrets missing." Same shape, different trigger. **This is fix-1 — ship first.** Without it every other fix below is advisory. ~0.5 dev-day.

2. **`get_status` returns git SHA + image tag + last-deploy-time.** Minimum fields: `deployed_sha`, `image_tag`, `deployed_at_utc`. Chatbot can now ground "you pushed 45e9d0d at 22:10; live is still at efb2616 from 20 min ago — your fix is NOT live yet." Directly closes the chatbot-grounding half of today's failure. ~0.5 dev-day.

3. **Per-deploy behavioral canary (not just 200 OK).** After deploy, probe a *fix-specific behavior* that proves the new code ran — e.g., for 7848f19 probe `patch_branch` with a string `input_keys` and assert the fail-loudly error (old code silent-char-splits, new code rejects). 200-OK-health-check ran green today while the fix was 30 min stale. Behavioral canary means "deploy green" ≡ "the thing we just fixed is actually fixed in the wild." ~0.5-1 dev-day per canary, add as we ship fixes.

4. **Image-build-from-canonical-env-template.** WIKI_PATH=C:\Users\... reached the droplet because someone hand-typed env values during cutover. Move to `deploy/env.template` + Docker build-time substitution; reject drift at deploy time. Eliminates the class-of-bug, not just the instance. ~1 dev-day.

5. **`/version` endpoint on MCP server.** Independent of `get_status` — cheaper, faster, and callable without MCP handshake. Layer-1 canary probes it; if it doesn't match expected SHA, alarm. Composes with fix-1 + fix-2. ~0.25 dev-day.

## Ship-first: fix-1 (deploy-failure alarm)

Prevents the exact failure we just lived: push, assume green, discover 30 min later it never deployed. Without fix-1, fix-2 through fix-5 all also silently rot the moment their own deploy-run fails. Fix-1 is the meta-guard.

## What we stop doing

- **Stop accepting "workflow run succeeded" as evidence of deploy.** The run ran — it also skipped past "Verify secrets" and opened a warning issue that no one read. Green workflow ≠ shipped code. Replace with: **"live surface serves new SHA OR alarm fires."**
- **Stop cluster-shipping fixes without a per-fix landing assertion.** Every non-trivial fix ships with a behavioral probe in `scripts/selfhost_smoke.py` that would have failed under the old code. Explicit assertion, not vibes.
- **Stop trusting the pre-cluster canary pattern to cover deploy.** Canary probes live behavior; it cannot tell you "the new commit is live." That requires version-grounding (fix-2) + deploy-green semantics tied to the *new* SHA (fix-1 + fix-5 composed).

Without this layer, every fix we ship is a guess. With it, we stop guessing.
