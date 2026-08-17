#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["selectolax>=0.3.21"]
# ///
"""Pin the skill-tree inventory that README section 1 and docs/METHOD.md section 1 publish.

    ./tests/test_parse_tree.py

Those documents quote 74 nodes, 35 prerequisite rows, 23 hardmode nodes and 4,790 attempt slots,
and the whole argument in sections 5-7 rests on the tree being shaped the way section 1 says it is.
If the parser or the committed snapshot ever drifts, the published numbers become wrong silently —
so they are asserted here against exact values rather than eyeballed.

This used to be four `grep -q` lines in the CI workflow. Substring greps accept any value whose
decimal expansion starts with the pinned digits ("74" matches "740"), and "4,790" matched anywhere
in the output including a per-tier subtotal, so the contract lived one layer above where it belongs
and was weaker than it looked.

Stdlib plus selectolax, no test runner. Exits non-zero on failure.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from parse_tree import PUZZLES_PER_QUIZ, parse

SNAPSHOT = Path(__file__).resolve().parent.parent / "data" / "skilltree-2026-08-16.html"

_failures: list[str] = []


def check(name: str, got: object, want: object) -> None:
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {name:<44} {got!r}" + ("" if ok else f"  want {want!r}"))
    if not ok:
        _failures.append(name)


def main() -> int:
    if not SNAPSHOT.exists():
        print(f"  FAIL  missing snapshot: {SNAPSHOT}")
        return 1

    d = parse(SNAPSHOT.read_text())
    nodes, rows, tiers = d["nodes"], d["rows"], d["tiers"]

    print("\nInventory published in README section 1 / METHOD.md section 1:")
    check("skill nodes", len(nodes), 74)
    check("prerequisite rows", len(rows), 35)
    check("hardmode nodes", sum(n["hardmode"] for n in nodes), 23)
    check("attempt slots to complete the tree", sum(n["attempt_slots"] for n in nodes), 4790)
    check("puzzles per quiz", PUZZLES_PER_QUIZ, 5)

    print("\nTier split (the three tiers, in the order section 1 lists them):")
    check("basics nodes", tiers["basics (30–18k)"], 20)
    check("intermediate nodes", tiers["intermediate (18–10k)"], 25)
    check("sdk nodes", tiers["sdk (9–1k)"], 29)
    check("no nodes fell outside a tier", tiers.get("unknown", 0), 0)

    print("\nStructure ranges quoted as '1-5 levels x 2-6 quizzes x 5 puzzles':")
    check("min levels per node", min(n["levels"] for n in nodes), 1)
    check("max levels per node", max(n["levels"] for n in nodes), 5)
    check("min quizzes per level", min(n["quizzes_per_level"] for n in nodes), 2)
    check("max quizzes per level", max(n["quizzes_per_level"] for n in nodes), 6)

    print("\nConcept-tag grid (the 3x5 vocabulary section 1 says needs no inventing):")
    tally = Counter(c for n in nodes for c in n["concepts"])
    phase = {"opening", "middle-game", "endgame"}
    check("phase tags", sorted(t for t in tally if t in phase), sorted(phase))
    check(
        "kind tags",
        sorted(t for t in tally if t not in phase),
        ["analysis", "fighting", "knowledge", "life-and-death", "tesuji"],
    )

    print("\nEvery node carries the attributes the inventory is built from:")
    check("nodes with a skill_id", sum(bool(n["skill_id"]) for n in nodes), 74)
    check("nodes with a label", sum(bool(n["label"]) for n in nodes), 74)
    check("nodes with >=1 concept tag", sum(bool(n["concepts"]) for n in nodes), 74)
    # The reduction for publication redacted data-nonce; nothing here may depend on it.
    check("parser ignores data-nonce", "nonce" in str(nodes[0].keys()), False)

    print()
    if _failures:
        print(f"  {len(_failures)} FAILED: {', '.join(_failures)}\n")
        return 1
    print("  all checks passed\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
