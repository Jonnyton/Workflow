---
status: shipped
shipped_date: 2026-04-19
---

# 2026-04-19 — Option-Select "No Preference" Bug (claude_chat.py)

**Status:** Fixed in this commit chain.
**Severity:** Persona-authenticity failure, blocks meaningful live-browser user-sim missions.
**Observed:** Maya live mission 2026-04-19 — Claude.ai presented a clarifying-question selection widget. User-sim expected to answer in Maya's voice. Actual behavior: auto-dismissed with a Skip-button click that the model interpreted as "user picked No preference / skipped."

---

## Root cause

`scripts/claude_chat.py::_try_recover_input` (the escalation ladder invoked when no free-text input is detected) had the following step order when the "ask-user-option" selection widget was present:

1. Click `main` area to refocus.
2. **Click `button[data-widget-action="true"]:has-text("Skip")`** — Claude.ai's widget Skip button. The prior hypothesis was that Skip dismissed the widget and re-mounted the input like Escape would, but with more reliability (doesn't depend on focus). This was documented in the prior regression test (`test_recovery_clicks_widget_skip_button_before_escape`).
3. Escape (twice if widget still visible).
4. Scroll-bottom.
5. Tab-cycle.
6. Reload chat URL → fallback Skip click.

**The assumption that Skip is a non-submitting dismiss is wrong.** Claude.ai's `ask-user-option` widget's Skip button is a **semantic choice the model sees** — clicking Skip posts "user skipped the question / no preference" into the conversation. The model proceeds assuming the user had no strong preference.

For a real phone user typing in persona voice, this is a lazy workaround: the persona wanted to say *"go with the invoice automation one — I'm a bookkeeper"* but the tool said "no preference" on her behalf.

Evidence locations:
- `output/claude_chat_failures/20260412T184237_input_not_found.html` — original widget DOM capture.
- `output/user_sim_session.md` Maya mission tail (~2026-04-19) — "chose No preference" symptom.
- Prior test at `tests/test_claude_chat_recovery.py:304` explicitly encoded the wrong behavior.

---

## Why prior fix landed wrong

When the widget appeared in early missions, user-sim got stuck with "input not found" errors and the mission stalled. The Skip-click was added as a *pragmatic unblock* — get the mission moving at all. The trade-off was not weighed: "unblock the mission" vs "answer faithfully in persona." Unblock-at-any-cost won by default because no one had named the second value out loud yet.

With user-sim now persona-driven (per `project_user_sim_persona_driven.md` 2026-04-19), persona authenticity is a first-class value. The Skip-click shortcut is no longer acceptable.

---

## Fix

**Remove automatic Skip-click from the recovery ladder.**

When the selection widget is detected, `_try_recover_input`:
1. Attempts Escape (non-submitting, dismisses widget without posting a choice).
2. If Escape doesn't restore the input, **returns None with a dedicated failure reason: `selection_widget_active`.** The caller (`cmd_ask`) already captures a failure dump + emits stderr. The new stderr message tells user-sim: "Selection widget is up; your next `ask` will be typed as a freeform reply per the skill doc." On Claude.ai, the free-text input comes back the moment a new message is posted to the thread, so the next typed ask auto-restores the flow.

**Critical:** Escape is attempted because some Claude.ai builds treat widget-Escape as "close the widget without making a choice." If Escape clears the widget + restores the input, we still haven't submitted anything, so user-sim's next ask carries their real persona answer. Escape is safe; Skip is not.

**Reload fallback (step 6) also stops clicking Skip.** If reload alone doesn't restore the input and the widget re-renders, we emit the same `selection_widget_active` diagnostic and return None.

---

## What user-sim does when the widget is up

Skill doc addition codifies this:

1. See `input_not_found ... selection_widget=visible` diagnostic.
2. **Do NOT give up.** Call `claude_chat.py ask "<persona's freeform answer>"`. The act of posting a new message re-mounts the input (Claude.ai treats the new user turn as implicit widget dismissal + proceeds with the typed content as the user's chosen reply).
3. If the persona genuinely has no preference, they type *"no preference either way, whatever you recommend"* — but that's the persona's decision, not the tool's default.

This is fully faithful to a real phone user: a real user stares at the picker, doesn't see a button that fits, types an answer into the chat box instead. Which is exactly what the skill doc's "always prefer free-response text" section already said. The tool was violating the skill doc by auto-clicking Skip.

---

## Regression tests

- `test_recovery_does_not_click_widget_skip` — widget visible, Escape restores input → `skip_click` NOT in steps, Escape called.
- `test_recovery_returns_none_when_widget_sticky` — widget visible + Escape doesn't clear it → `_try_recover_input` returns None; caller's failure dump fires with `selection_widget=visible`.
- The prior tests (`test_recovery_clicks_widget_skip_button_before_escape`, `test_recovery_reload_then_skip_when_widget_rerenders`) are deleted. They encoded the bug.

---

## Follow-up

Prior to this fix, user-sim learned to route around the buggy Skip-click by priming the bot ("I'll reply in text — treat my next message as my choice"). Skill doc's "when Claude.ai presents selectable options" section already recommended this. With the fix landed, priming is no longer required — user-sim can just type. Keep the priming guidance in the skill as a resilient fallback for exotic widget variants that ignore Escape.

---

## Cross-references

- Memory `feedback_option_select_no_preference_bug.md` — host's original report + directive for both skill fix + user-sim discipline.
- Memory `project_user_sim_persona_driven.md` — persona-authenticity rationale.
- `.agents/skills/ui-test/SKILL.md` §"CRITICAL — when Claude.ai presents selectable options" — user-sim-facing section updated in this commit chain.
- `scripts/claude_chat.py::_try_recover_input` — fix site.
- `tests/test_claude_chat_recovery.py` — test updates.
