#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Assemble a Go problem collection on Go Magic's (phase x concept) grid.

    ./src/build_collection.py --list           # what is reusable, and under what licence
    ./src/build_collection.py --fetch ggg      # download one source into out/collection/
    ./src/build_collection.py --index          # normalise what is downloaded into an index

Why this fetches rather than ships
----------------------------------
Almost every convenient Go problem collection is either copyrighted or unlicensed, and the two
sets that *are* open carry terms this repo cannot absorb: Go Game Guru's problems are
CC BY-NC-SA (NonCommercial, and ShareAlike is incompatible with this repo's MIT licence), and
Sensei's Library is under the Open Content License, whose copyleft is viral over the whole
derivative. So the repo ships the *index* and this *fetcher*; the problems themselves land in
`out/collection/`, which is not tracked. You acquire them under their licence, not under ours.

`data/problem_sources.json` records what was checked, including the thirteen sources that are NOT
reusable — several of which look safe and are not. Read it before adding a source here.

The phase classifier
--------------------
No external source emits a (phase, concept) pair: the common 7-value vocabulary gives phase or
concept but never both, and ~92% of the world's tagged problems are tesuji or life-and-death, so
they arrive with phase blank. Phase is recoverable from the SGF itself, and `infer_phase` is a
deliberately crude first cut at that — stone count and board coverage only. It is reported with a
confidence so that a downstream consumer can ignore the guesses, and it is the obvious place for
a better model.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = json.loads((ROOT / "data" / "problem_sources.json").read_text())
OUT = ROOT / "out" / "collection"

# The manifest is the source of truth for where a source lives and under what licence; the
# fetcher derives its URLs from it rather than restating repo, branch and path as literals.
GGG = next(s for s in SOURCES["reusable"] if s["id"] == "ggg-weekly")


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "gomagic-glicko/build_collection"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def cmd_list() -> None:
    print(f"\n  {'source':<26}{'problems':>10}  {'difficulty':<14}{'licence':<24}fetchable")
    print(f"  {'-'*26}{'-'*10}  {'-'*14}{'-'*24}{'-'*9}")
    for s in SOURCES["reusable"]:
        d = s["difficulty"]["scheme"]
        lic = s["licence"].get("spdx", "?")
        print(f"  {s['id']:<26}{s['problems']:>10}  {d:<14}{lic:<24}"
              f"{'yes' if 'fetch' in s else 'manual'}")
    print(f"\n  {len(SOURCES['not_reusable'])} sources were checked and rejected — see "
          f"data/problem_sources.json.\n  Several of them look safe and are not.\n")
    for s in SOURCES["reusable"]:
        if s.get("blocks"):
            print(f"  {s['id']}: {'; '.join(s['blocks'])}")
    print()


def fetch_ggg() -> tuple[int, int]:
    """Go Game Guru's 422 weekly problems. CC BY-NC-SA: attribute, non-commercial, share alike.

    Returns (newly downloaded, total in the source)."""
    dest = OUT / "ggg"
    dest.mkdir(parents=True, exist_ok=True)
    repo = GGG["url"].removeprefix("https://github.com/")
    branch, prefix = GGG["fetch"]["branch"], GGG["fetch"]["path"]
    tree = json.loads(_get(f"https://api.github.com/repos/{repo}/git/trees/{branch}?recursive=1"))
    if tree.get("truncated"):
        sys.exit("the GitHub tree listing came back truncated — the fetch would be silently "
                 "incomplete. Fetch by subdirectory instead.")
    paths = [n["path"] for n in tree["tree"]
             if n["path"].lower().endswith(".sgf") and n["path"].startswith(prefix + "/")]
    todo = []
    for p in paths:
        target = dest / Path(p).relative_to(prefix)
        if not target.exists():
            todo.append((p, target))

    def grab(item: tuple[str, Path]) -> None:
        p, target = item
        target.parent.mkdir(parents=True, exist_ok=True)
        # Write-then-rename, so a run killed mid-download cannot leave a truncated .sgf that
        # the target.exists() resume check above would forever mistake for a finished one.
        tmp = target.with_suffix(target.suffix + ".part")
        tmp.write_bytes(_get(f"https://raw.githubusercontent.com/{repo}/{branch}/"
                             + urllib.parse.quote(p)))
        tmp.replace(target)

    # The files are tiny and independent, so a sequential fetch is nothing but connection
    # latency; a small pool cuts the cold run ~10x while staying polite to the host.
    with ThreadPoolExecutor(max_workers=8) as ex:
        for done, _ in enumerate(ex.map(grab, todo), start=1):
            if done % 50 == 0:
                print(f"    {done}/{len(todo)}")

    (dest / "ATTRIBUTION.txt").write_text(
        f"{GGG['name']} — {GGG['url']}\n"
        f"Licensed {GGG['licence']['spdx']}; verification in data/problem_sources.json.\n"
        "NonCommercial: not usable in a paid product. ShareAlike: derivatives must carry the\n"
        "same licence, which is why these files are NOT committed to this MIT-licensed repo.\n")
    return len(todo), len(paths)


def infer_phase(sgf: str) -> tuple[str, str]:
    """Guess the game phase from the position. Returns (phase, confidence).

    Crude on purpose: stone count alone separates opening from the rest reasonably well, because a
    problem needs enclosed shape to be a problem, and enclosure takes stones. It cannot separate
    middle-game from endgame — that needs whether the rest of the board is settled, which a single
    problem diagram does not show. Those come back 'middle-game' with confidence 'low'.
    """
    # Count setup stones: coordinate values before the first move node. A move node is ";B[" or
    # ";W[" whether or not it opens a variation — GGG's files all branch at move one ("(;B"),
    # but a plain main line does not, and cutting only at "(;B" would count every main-line
    # move as a setup stone.
    stones = len(re.findall(r"\[[a-s]{2}\]", re.split(r";[BW]\[", sgf, maxsplit=1)[0]))
    size_m = re.search(r"SZ\[(\d+)\]", sgf)
    size = int(size_m.group(1)) if size_m else 19
    if size < 19:
        return "middle-game", "low"          # small-board problems are phase-ambiguous
    if stones <= 6:
        return "opening", "low"
    return "middle-game", "low"


def cmd_index() -> None:
    """Normalise whatever has been fetched into one index on the Go Magic grid."""
    ggg = OUT / "ggg"
    if not ggg.exists():
        sys.exit("nothing fetched yet — run: ./src/build_collection.py --fetch ggg")

    records = []
    # Suffix matched case-insensitively, as the fetch filter does — an upstream "Foo.SGF" must
    # not be fetched on one side and skipped on the other.
    for f in sorted(p for p in ggg.rglob("*") if p.suffix.lower() == ".sgf"):
        sgf = f.read_text(errors="replace")
        band = f.parent.name
        phase, conf = infer_phase(sgf)
        records.append({
            "id": f"ggg/{f.parent.name}/{f.stem}",
            "source": GGG["id"],
            "licence": GGG["licence"]["spdx"],
            "path": str(f.relative_to(ROOT)),
            # Difficulty is the directory: the source's own 3-band grading, which its README
            # concedes is subjective. Kept as the source's label rather than mapped to a rank,
            # because there is no published equating from these bands to kyu/dan.
            "difficulty_band": band if band != "other" else None,
            "difficulty_rank": None,
            "phase": phase,
            "phase_confidence": conf,
            # GGG carries no concept tag. Left null rather than guessed: the whole point of the
            # taxonomy work is that inventing a concept label is worse than admitting it is absent.
            "concept": None,
            "concept_source": "unlabelled",
        })

    (OUT / "index.json").write_text(json.dumps(
        {"_about": "Normalised index of fetched Go problems on Go Magic's (phase x concept) grid. "
                   "Content stays under its own licence in this directory and is not committed.",
         "count": len(records), "records": records}, indent=2))

    by_band = Counter(str(r["difficulty_band"]) for r in records)
    by_phase = Counter(r["phase"] for r in records)
    print(f"\n  indexed {len(records)} problems -> {OUT / 'index.json'}")
    print(f"  difficulty: {dict(by_band)}")
    print(f"  phase (inferred, low confidence): {dict(by_phase)}")
    print(f"  concept: unlabelled for all {len(records)} — GGG carries no concept tag\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    cmd = ap.add_mutually_exclusive_group()
    cmd.add_argument("--list", action="store_true",
                     help="show reusable sources and their licences (the default)")
    cmd.add_argument("--fetch", choices=["ggg"], help="download a source into out/collection/")
    cmd.add_argument("--index", action="store_true", help="normalise what is downloaded")
    args = ap.parse_args()

    if args.fetch == "ggg":
        new, total = fetch_ggg()
        print(f"  fetched {new} new SGF ({total} in the source) into {OUT / 'ggg'} "
              f"(CC BY-NC-SA, not committed)")
    elif args.index:
        cmd_index()
    else:
        cmd_list()


if __name__ == "__main__":
    main()
