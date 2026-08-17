#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["selectolax"]
# ///
"""
Parse Go Magic's public Skill Tree into a structured inventory.

Everything here comes from server-rendered HTML at https://gomagic.org/go-problems/
(the `/skills/` URL 301s there). The whole data model is in `data-*` attributes, so this
is reading a public page, not reverse-engineering anything.

    ./parse_tree.py                    # fetch live and summarise
    ./parse_tree.py --html data/skilltree.html
    ./parse_tree.py --json out/tree.json

Why this matters for the Glicko-2 argument
------------------------------------------
Each node carries `data-level_qty` levels and `data-quiz_qty` quizzes per level, and the page
states 5 puzzles per quiz. Multiply out and you get the number of puzzle *attempt slots* the
tree contains — which is the sample size any difficulty estimate would be built from.

Difficulty today comes from a static hand-assigned band per node. Nothing in this markup is a
measurement.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

from selectolax.parser import HTMLParser

URL = "https://gomagic.org/go-problems/"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/121"

PUZZLES_PER_QUIZ = 5  # stated on the page: "a quiz — a short series of 5 puzzles"


def fetch(url: str = URL) -> str:
    out = subprocess.run(
        ["curl", "-sL", "-A", UA, "--max-time", "40", url],
        capture_output=True, text=True,
    )
    if out.returncode != 0 or len(out.stdout) < 10_000:
        sys.exit(f"fetch failed (rc={out.returncode}, {len(out.stdout)} bytes)")
    return out.stdout


def parse(html: str) -> dict:
    tree = HTMLParser(html)
    nodes = []

    # Tier lives on the enclosing row: `class="skill_tree_row sdk_tree"`. Walk up from each
    # node rather than guessing from document order.
    TIERS = {"basics_tree": "basics (30–18k)",
             "inter_tree": "intermediate (18–10k)",
             "sdk_tree": "sdk (9–1k)"}

    def tier_of(el) -> str:
        p = el.parent
        while p is not None:
            cls = (p.attributes.get("class") or "") if p.attributes else ""
            for key, name in TIERS.items():
                if key in cls:
                    return name
            p = p.parent
        return "unknown"

    for el in tree.css("div.gomagic_skill"):
        a = el.attributes

        def num(key: str, default: int = 0) -> int:
            v = a.get(key) or ""
            return int(v) if v.strip().isdigit() else default

        # The visible label lives in a descendant; take the first non-empty text.
        label = ""
        for child in el.iter(include_text=False):
            t = (child.text() or "").strip()
            if t and len(t) < 80:
                label = " ".join(t.split())
                break

        skills = [s for s in (a.get("data-basic_skills") or "").split(",") if s]
        levels, quizzes = num("data-level_qty"), num("data-quiz_qty")

        nodes.append({
            "skill_id": a.get("data-skill_id"),
            "label": label,
            "levels": levels,
            "quizzes_per_level": quizzes,
            "attempt_slots": levels * quizzes * PUZZLES_PER_QUIZ,
            "concepts": skills,
            "hardmode": bool((a.get("data-allow_hardmode") or "").strip()),
            "state": a.get("data-skill_state") or "",
            "tier": tier_of(el),
        })

    # Rows encode the prerequisite ordering: progression is row-by-row, not a free DAG.
    rows = sorted({
        el.attributes.get("data-skill_row_id")
        for el in tree.css("[data-skill_row_id]")
        if el.attributes.get("data-skill_row_id")
    }, key=lambda x: int(x) if x.isdigit() else 0)

    tiers = Counter(n["tier"] for n in nodes)

    return {"nodes": nodes, "rows": rows, "tiers": tiers}


def summarise(d: dict) -> None:
    nodes, rows, tiers = d["nodes"], d["rows"], d["tiers"]
    total_slots = sum(n["attempt_slots"] for n in nodes)

    print()
    print(f"  Skill nodes            {len(nodes)}")
    print(f"  Prerequisite rows      {len(rows)}   (row-by-row, not a DAG)")
    for t, c in sorted(tiers.items()):
        slots = sum(n["attempt_slots"] for n in nodes if n["tier"] == t)
        print(f"  Tier {t:<24} {c:>3} nodes  {slots:>6,} slots")
    print(f"  Hardmode nodes         {sum(n['hardmode'] for n in nodes)}")
    print(f"  Levels per node        {min(n['levels'] for n in nodes)}–{max(n['levels'] for n in nodes)}")
    print(f"  Quizzes per level      {min(n['quizzes_per_level'] for n in nodes)}–{max(n['quizzes_per_level'] for n in nodes)}")
    print(f"  Puzzles per quiz       {PUZZLES_PER_QUIZ}   (stated on the page)")
    print(f"  ── attempt slots       {total_slots:,}   to complete the whole tree")
    print()

    tally = Counter(c for n in nodes for c in n["concepts"])
    print("  Concept tags — the vocabulary a mistake-classifier would target:")
    phase = [c for c in tally if c in {"opening", "middle-game", "endgame"}]
    kind = [c for c in tally if c not in phase]
    print(f"    phase  ({len(phase)}): " + ", ".join(f"{c} ×{tally[c]}" for c in sorted(phase)))
    print(f"    kind   ({len(kind)}): " + ", ".join(f"{c} ×{tally[c]}" for c in sorted(kind)))
    print()
    print("  Nothing above is a measurement. Difficulty is a hand-assigned band per node.")
    print()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--html", type=Path, help="parse a saved copy instead of fetching")
    ap.add_argument("--json", type=Path, help="write the parsed inventory here")
    args = ap.parse_args()

    html = args.html.read_text() if args.html else fetch()
    d = parse(html)
    if not d["nodes"]:
        sys.exit("no skill nodes found — the page markup may have changed")

    summarise(d)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(d, indent=2))
        print(f"  wrote {args.json}\n")


if __name__ == "__main__":
    main()
