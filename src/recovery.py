#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["matplotlib", "numpy"]
# ///
"""
How many attempts does it take to *measure* a puzzle's difficulty?

    ./recovery.py                        # the full sweep, writes out/recovery.png
    ./recovery.py --quick                # fewer reps, for iterating
    ./recovery.py --puzzles 500 --players 2000

What this does and does not claim
---------------------------------
It does **not** claim Go Magic's hand-assigned difficulty labels are wrong. Nobody outside the
company can know that; it needs their attempt log.

It answers the question that comes *before* that one: **if you ran Glicko-2 over an attempt log,
how much data would you need before the answer meant anything?** That is a property of the
estimator and the shape of the data, and it can be settled by simulation.

Method: plant puzzles with known true difficulties and players with known true skills, simulate
first attempts, fit Glicko-2 knowing neither, and measure how close the fitted difficulties get
to the planted ones as the number of attempts per puzzle grows.

The part that matters
---------------------
A skill tree does not serve random puzzles. Progression is gated, so players only meet puzzles
near their own level, and the attempt matrix is *banded* rather than dense. Restriction of range
is the classic way an estimate like this degrades, so the sweep runs both regimes and reports the
difference. If banded selection needs materially more data, that is a design constraint on any
adaptive-difficulty feature, not a detail.
"""

from __future__ import annotations

import argparse
import math
import random
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from glicko2 import DEFAULT_RATING, Rating, play  # noqa: E402

# Rough mapping used only to make the simulated spread realistic: Go ranks are roughly linear in
# rating over the kyu range, ~100 points per rank. 20k ≈ 700, 1d ≈ 2100 on this scale.
RANK_SPREAD = 1400.0


@dataclass
class Sim:
    puzzles: list[float]   # true difficulty
    players: list[float]   # true skill


def make_world(n_puzzles: int, n_players: int, rng: random.Random) -> Sim:
    """Plant a population. Difficulties and skills both span the kyu range."""
    puzzles = [rng.gauss(DEFAULT_RATING, RANK_SPREAD / 3) for _ in range(n_puzzles)]
    players = [rng.gauss(DEFAULT_RATING, RANK_SPREAD / 3) for _ in range(n_players)]
    return Sim(puzzles, players)


def solves(skill: float, difficulty: float, rng: random.Random) -> bool:
    """Logistic outcome on the true latent values. 400-point scale, as in Elo."""
    p = 1.0 / (1.0 + 10 ** ((difficulty - skill) / 400.0))
    return rng.random() < p


def simulate(sim: Sim, attempts_per_puzzle: int, banded: bool, rng: random.Random,
             band: float = 300.0, linking: float = 0.0) -> tuple[list[Rating], list[Rating]]:
    """Run an attempt log through Glicko-2 and return the fitted (puzzles, players).

    `banded=True` models skill-tree gating: a player only meets puzzles within `band` points of
    their own level. `banded=False` is the diagnostic-test regime, where anyone can meet anything.

    `linking` is the fraction of attempts drawn *ungated* even in the banded regime. This is the
    psychometric remedy for a poorly-connected design: a few common items spanning the whole
    range, seen by everyone, pin the scale together. Go Magic already owns the instrument for
    this — the Go Diagnostics test is not gated by the tree.
    """
    pz = [Rating() for _ in sim.puzzles]
    pl = [Rating() for _ in sim.players]

    # Build the attempt list first so both regimes see the same total volume.
    attempts: list[tuple[int, int]] = []
    for zi, zdiff in enumerate(sim.puzzles):
        use_band = banded and rng.random() >= linking
        if use_band:
            pool = [i for i, s in enumerate(sim.players) if abs(s - zdiff) <= band]
            if len(pool) < attempts_per_puzzle:
                pool = sorted(range(len(sim.players)),
                              key=lambda i: abs(sim.players[i] - zdiff))[:attempts_per_puzzle]
        else:
            pool = range(len(sim.players))
        chosen = rng.sample(list(pool), min(attempts_per_puzzle, len(pool)))
        attempts.extend((pi, zi) for pi in chosen)

    # Order matters to an online estimator, and a real log is chronological, not grouped.
    rng.shuffle(attempts)

    for pi, zi in attempts:
        won = solves(sim.players[pi], sim.puzzles[zi], rng)
        pl[pi], pz[zi] = play(pl[pi], pz[zi], won)

    return pz, pl


def spearman(a: list[float], b: list[float]) -> float:
    """Rank correlation, to separate 'wrong order' from 'right order, drifted scale'."""
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        for pos, i in enumerate(order):
            r[i] = float(pos)
        return r
    ra, rb = ranks(a), ranks(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return num / den if den else float("nan")


def score(fitted: list[Rating], truth: list[float]) -> tuple[float, float, float]:
    """Return (RMSE, share within +/-100, share within +/-200) after removing the mean offset.

    The offset removal matters: Glicko-2 fixes no absolute origin, so the whole scale can float.
    Only *relative* difficulty is identifiable, and that is the thing a difficulty label needs.
    """
    seen = [(f.rating, t) for f, t in zip(fitted, truth) if f.games > 0]
    if not seen:
        return float("nan"), 0.0, 0.0
    offset = sum(f - t for f, t in seen) / len(seen)
    errs = [abs((f - offset) - t) for f, t in seen]
    rmse = math.sqrt(sum(e * e for e in errs) / len(errs))
    rho = spearman([f for f, _ in seen], [t for _, t in seen])
    return rmse, sum(e <= 100 for e in errs) / len(errs), rho


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--puzzles", type=int, default=400)
    ap.add_argument("--players", type=int, default=3000)
    ap.add_argument("--reps", type=int, default=3, help="repeats per point, averaged")
    ap.add_argument("--quick", action="store_true", help="one rep, fewer sample sizes")
    ap.add_argument("--seed", type=int, default=20260816)
    ap.add_argument("--out", type=Path, default=Path("out/recovery.png"))
    args = ap.parse_args()

    sweep = [5, 10, 20, 40] if args.quick else [3, 5, 10, 20, 40, 80, 160]
    reps = 1 if args.quick else args.reps

    print(f"\n  {args.puzzles} puzzles, {args.players} players, {reps} rep(s) per point")
    print(f"  outcome model: logistic on true skill minus true difficulty, 400-point scale\n")
    print(f"  {'attempts':>9}  {'regime':<8}  {'RMSE':>7}  {'±100':>6}  {'rho':>6}")
    print(f"  {'-'*9}  {'-'*8}  {'-'*7}  {'-'*6}  {'-'*6}")

    regimes = [("random", False, 0.0), ("banded", True, 0.0), ("banded+10% link", True, 0.10)]
    results: dict[str, list[tuple[int, float, float]]] = {r[0]: [] for r in regimes}
    for n in sweep:
        for regime, banded, linking in regimes:
            rs, w1s = [], []
            for r in range(reps):
                rng = random.Random(args.seed + r * 977 + n)
                sim = make_world(args.puzzles, args.players, rng)
                pz, _ = simulate(sim, n, banded, rng, linking=linking)
                rmse, w100, rho = score(pz, sim.puzzles)
                rs.append(rmse); w1s.append(w100)
                if r == reps - 1:
                    print(f"  {n:>9}  {regime:<8}  {sum(rs)/len(rs):>7.1f}  "
                          f"{sum(w1s)/len(w1s):>5.0%}  {rho:>6.2f}")
            results[regime].append((n, sum(rs) / len(rs), sum(w1s) / len(w1s)))

    print()
    _plot(results, args.out, args.puzzles, args.players)


def _plot(results: dict, out: Path, n_puzzles: int, n_players: int) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7.5, 4.6), dpi=160)
    styles = {"random": ("#2563eb", "o", "random pairing (ungated diagnostic)"),
              "banded": ("#dc2626", "s", "banded pairing (skill-tree gating)"),
              "banded+10% link": ("#16a34a", "^", "banded + 10% ungated linking items")}

    for regime, pts in results.items():
        if not pts:
            continue
        colour, marker, label = styles.get(regime, ("#888", "x", regime))
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        ax.plot(xs, ys, marker=marker, color=colour, lw=2, ms=5, label=label)

    ax.set_xscale("log")
    ax.set_xlabel("first attempts per puzzle")
    ax.set_ylabel("difficulty recovery error (RMSE, rating points)")
    ax.set_title("How much data before a puzzle's difficulty is measured?", loc="left", fontsize=11)
    ax.axhline(100, color="#64748b", ls=":", lw=1)
    ax.text(ax.get_xlim()[0] * 1.05, 104, "±100 points ≈ one Go rank", fontsize=8, color="#64748b")
    ax.grid(alpha=0.25, which="both")
    ax.legend(frameon=False, fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    fig.text(0.01, 0.01,
             f"simulation: {n_puzzles} puzzles, {n_players} players, Glicko-2 with Lichess clamps. "
             f"Shows what it would take to measure difficulty, not that any label is wrong.",
             fontsize=6.5, color="#64748b")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    print(f"  wrote {out}\n")


if __name__ == "__main__":
    main()
