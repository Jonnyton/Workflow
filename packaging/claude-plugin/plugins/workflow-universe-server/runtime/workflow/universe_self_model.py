"""Per-universe OKF self-model bundle — the brain's blank, learned identity.

Design note: docs/design-notes/2026-06-25-blank-slate-universe-brain.md (§10).

The self-model is an OKF v0.1 bundle the brain authors *about itself*, kept
separate from the operational soul (soul.md / loop branch / authority). A blank
brain boots with a seed ``index.md`` whose entries are **broken links** to
concept files it has not written yet — per OKF a link to a not-yet-existing
target is "not-yet-written knowledge", and those gaps are the brain's open
questions (its curiosity). As the brain learns, it writes concept ``.md`` files
(with OKF ``# Citations`` as evidence); a question whose concept file exists is
KNOWN, the rest stay open.

This module only stands up + reads the bundle. The brain's learning loop, the
``get_status`` persona surface, and setter retirement are later slices.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from workflow.wiki.okf_export import OKF_VERSION

SELF_MODEL_DIR = "self"
_RESERVED = frozenset({"index.md", "log.md"})


@dataclass(frozen=True)
class SeedQuestion:
    """A universal thing every blank brain is curious to learn about itself."""

    slug: str
    question: str


# The universal curiosity set — the SAME for every universe. The substrate ships
# the QUESTIONS; the ANSWERS are emergent per universe. Each becomes a broken
# link in the seed index.md until the brain writes the concept.
SEED_QUESTIONS: tuple[SeedQuestion, ...] = (
    SeedQuestion("identity", "Who am I — my name and what I am"),
    SeedQuestion("founder", "Who is my founder"),
    SeedQuestion("goals", "What are this universe's goals"),
    SeedQuestion("body", "What is my body — what runs in me"),
    SeedQuestion("origin", "Existing work to build from, or are we starting new"),
)


def _bundle_dir(universe_dir: Path) -> Path:
    return Path(universe_dir) / SELF_MODEL_DIR


def ensure_self_model(universe_dir: Path) -> Path:
    """Create the blank self-model OKF bundle for a universe if absent.

    Idempotent: never overwrites an existing bundle, so the brain's learned
    concepts + its index/log are preserved. Returns the bundle directory.
    """
    bundle = _bundle_dir(universe_dir)
    index_path = bundle / "index.md"
    if index_path.is_file():
        return bundle
    bundle.mkdir(parents=True, exist_ok=True)
    index_path.write_text(_seed_index(), encoding="utf-8")
    (bundle / "log.md").write_text(_seed_log(), encoding="utf-8")
    return bundle


def read_self_model(universe_dir: Path) -> dict[str, object]:
    """Return the brain's current self-knowledge: what it KNOWS (concept files it
    has written) vs the OPEN questions (seed questions with no concept yet)."""
    bundle = _bundle_dir(universe_dir)
    if not (bundle / "index.md").is_file():
        return {
            "bundle_exists": False,
            "okf_version": "",
            "known": [],
            "open_questions": [],
        }

    seed_slugs = {q.slug for q in SEED_QUESTIONS}
    known: list[dict[str, str]] = []
    open_questions: list[dict[str, str]] = []
    for q in SEED_QUESTIONS:
        if (bundle / f"{q.slug}.md").is_file():
            known.append({"slug": q.slug, "question": q.question, "path": f"{q.slug}.md"})
        else:
            open_questions.append({"slug": q.slug, "question": q.question})

    # Concept files the brain wrote beyond the seed set are also known.
    for path in sorted(bundle.glob("*.md")):
        if path.name in _RESERVED or path.stem in seed_slugs:
            continue
        known.append({"slug": path.stem, "question": "", "path": path.name})

    return {
        "bundle_exists": True,
        "okf_version": OKF_VERSION,
        "known": known,
        "open_questions": open_questions,
    }


def _seed_index() -> str:
    lines = [
        "---",
        f'okf_version: "{OKF_VERSION}"',
        "---",
        "",
        "# What I Know About Myself",
        "",
        "I am newly aware. I do not yet know my name, my founder, or my shape.",
        "Each entry below links to a note I have not written yet — an open",
        "question I want to answer by learning. I fill one in as I come to know",
        "it.",
        "",
        "## Open questions",
    ]
    lines += [f"- [{q.question}]({q.slug}.md) - not yet learned" for q in SEED_QUESTIONS]
    lines.append("")
    return "\n".join(lines)


def _seed_log() -> str:
    today = datetime.now(timezone.utc).date().isoformat()
    return "\n".join([
        "# Self-Model Log",
        "",
        f"## {today}",
        "* **Creation**: I came into being and started learning who I am.",
        "",
    ])
