#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["matplotlib>=3.8"]
# ///
"""
How many attempts does it take to *measure* a puzzle's difficulty?

    ./recovery.py                        # the full sweep, writes out/recovery.png
    ./recovery.py --quick                # fewer reps, for iterating
    ./recovery.py --puzzles 500 --players 2000
    ./recovery.py --linking 0.25 0.5 1.0 # the linking-item dose-response

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

Two error numbers, and why both are reported
--------------------------------------------
Neither estimator fixes an origin, so a raw RMSE against the planted values is meaningless. But
there are two different ways to take that out, and they answer different questions:

  * `rmse_offset` removes only a mean offset. It preserves the fitted *scale*, so it still
    penalises an estimator that gets the ordering right and the spacing wrong.
  * `rmse_affine` removes a full least-squares affine map. It is scale-free by construction —
    algebraically it equals sd(truth) * sqrt(1 - r^2), i.e. it is Pearson correlation wearing
    rating-point units, and it cannot see scale error at all.

Reporting only the second one would hide exactly the failure mode this experiment is looking for,
so `slope` is printed alongside: 1.0 means the fitted scale is already correct and the two RMSEs
agree; far from 1.0 means the affine number is flattering the estimator.
"""

from __future__ import annotations

import argparse
import math
import random
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from glicko2 import DEFAULT_RATING, Rating, play

# Rough mapping used only to make the simulated spread realistic: Go ranks are roughly linear in
# rating over the kyu range, ~100 points per rank. 20k ≈ 700, 1d ≈ 2100 on this scale.
RANK_SPREAD = 1400.0
TRUE_SD = RANK_SPREAD / 3.0   # the sd both planted populations are drawn with

# (player index, puzzle index, 1.0 solved / 0.0 failed)
Attempt = tuple[int, int, float]


@dataclass
class Sim:
    puzzles: list[float]   # true difficulty
    players: list[float]   # true skill


@dataclass
class Score:
    """How close a set of fitted ratings got to the planted truth. See the module docstring."""
    rmse_offset: float    # scale-preserving: mean offset removed only
    rmse_affine: float    # scale-free: full affine map removed
    slope: float          # the affine slope; 1.0 == the fitted scale is already right
    within_100: float     # share inside +/-100 points under offset-only alignment
    rho: float            # Spearman rank correlation


def make_world(n_puzzles: int, n_players: int, rng: random.Random) -> Sim:
    """Plant a population. Difficulties and skills both span the kyu range."""
    puzzles = [rng.gauss(DEFAULT_RATING, TRUE_SD) for _ in range(n_puzzles)]
    players = [rng.gauss(DEFAULT_RATING, TRUE_SD) for _ in range(n_players)]
    return Sim(puzzles, players)


def solves(skill: float, difficulty: float, rng: random.Random) -> bool:
    """Logistic outcome on the true latent values. 400-point scale, as in Elo."""
    p = 1.0 / (1.0 + 10 ** ((difficulty - skill) / 400.0))
    return rng.random() < p


def make_log(sim: Sim, attempts_per_puzzle: int, banded: bool, rng: random.Random,
             band: float = 300.0, linking: float = 0.0) -> list[Attempt]:
    """Generate the attempt log: who tried what, and whether they solved it.

    This is the single source of the attempt log. Both estimators — online Glicko-2 in `replay`
    below, and the joint fit in `batch_fit.py` — are scored on the *same* list returned from here,
    which is the only way the online-vs-batch comparison is a comparison of estimators rather
    than of two different random draws.

    `banded=True` models skill-tree gating: a player only meets puzzles within `band` points of
    their own level. `banded=False` is the diagnostic-test regime, where anyone can meet anything.

    `linking` is the fraction of *puzzles* served ungated even in the banded regime — common items
    spanning the whole range, seen by everyone. That is the psychometric remedy for a poorly
    connected design: they pin the scale together. Because every puzzle gets the same number of
    attempts, this is also the fraction of ungated traffic. Go Magic already owns the instrument
    for this — the Go Diagnostics test is not gated by the tree.
    """
    everyone = range(len(sim.players))
    pairs: list[tuple[int, int]] = []
    for zi, zdiff in enumerate(sim.puzzles):
        # Drawn unconditionally, so every regime consumes the same rng stream and the regimes
        # stay paired on one planted world.
        ungated = rng.random() < linking
        if banded and not ungated:
            pool = [i for i, s in enumerate(sim.players) if abs(s - zdiff) <= band]
            if len(pool) < attempts_per_puzzle:
                pool = sorted(everyone, key=lambda i: abs(sim.players[i] - zdiff))[
                    :attempts_per_puzzle]
        else:
            pool = everyone
        pairs.extend((pi, zi) for pi in rng.sample(pool, min(attempts_per_puzzle, len(pool))))

    # Order matters to an online estimator, and a real log is chronological, not grouped.
    rng.shuffle(pairs)
    return [(pi, zi, 1.0 if solves(sim.players[pi], sim.puzzles[zi], rng) else 0.0)
            for pi, zi in pairs]


def replay(log: list[Attempt], n_players: int, n_puzzles: int,
           weight: float = 1.0) -> tuple[list[Rating], list[Rating]]:
    """Run an attempt log through online Glicko-2 and return the fitted (puzzles, players)."""
    pz = [Rating() for _ in range(n_puzzles)]
    pl = [Rating() for _ in range(n_players)]
    for pi, zi, outcome in log:
        pl[pi], pz[zi] = play(pl[pi], pz[zi], outcome > 0.5, weight)
    return pz, pl


def simulate(sim: Sim, attempts_per_puzzle: int, banded: bool, rng: random.Random,
             band: float = 300.0, linking: float = 0.0) -> tuple[list[Rating], list[Rating]]:
    """Build a log and fit it online. The two halves are separate so `batch_fit` can share one."""
    log = make_log(sim, attempts_per_puzzle, banded, rng, band=band, linking=linking)
    return replay(log, len(sim.players), len(sim.puzzles))


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
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb, strict=True))
    den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return num / den if den else float("nan")


def score_values(fitted: list[float], truth: list[float]) -> Score:
    """Score already-extracted numbers against the planted truth, both metrics at once."""
    n = len(fitted)
    if n == 0:
        return Score(float("nan"), float("nan"), float("nan"), 0.0, float("nan"))

    # Scale-preserving: take out the mean offset only.
    offset = sum(f - t for f, t in zip(fitted, truth, strict=True)) / n
    errs = [abs((f - offset) - t) for f, t in zip(fitted, truth, strict=True)]
    rmse_offset = math.sqrt(sum(e * e for e in errs) / n)

    # Scale-free: least-squares affine map of `fitted` onto `truth`, in closed form.
    mf = sum(fitted) / n
    mt = sum(truth) / n
    var_f = sum((f - mf) ** 2 for f in fitted)
    cov = sum((f - mf) * (t - mt) for f, t in zip(fitted, truth, strict=True))
    slope = cov / var_f if var_f else float("nan")
    intercept = mt - slope * mf
    resid = [(slope * f + intercept) - t for f, t in zip(fitted, truth, strict=True)]
    rmse_affine = math.sqrt(sum(r * r for r in resid) / n)

    return Score(rmse_offset, rmse_affine, slope,
                 sum(e <= 100 for e in errs) / n, spearman(fitted, truth))


def score(fitted: list[Rating], truth: list[float]) -> Score:
    """Score fitted `Rating`s, skipping any competitor that never played."""
    seen = [(f.rating, t) for f, t in zip(fitted, truth, strict=True) if f.games > 0]
    return score_values([f for f, _ in seen], [t for _, t in seen])


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--puzzles", type=int, default=400)
    ap.add_argument("--players", type=int, default=3000)
    ap.add_argument("--reps", type=int, default=3, help="repeats per point, averaged")
    ap.add_argument("--quick", action="store_true", help="one rep, fewer sample sizes")
    ap.add_argument("--band", type=float, default=300.0,
                    help="gating width: a player only meets puzzles within this many points")
    ap.add_argument("--linking", type=float, nargs="*", default=[0.10],
                    help="ungated fractions to sweep alongside the pure regimes")
    ap.add_argument("--seed", type=int, default=20260816)
    ap.add_argument("--out", type=Path, default=Path("out/recovery.png"))
    args = ap.parse_args()

    sweep = [5, 10, 20, 40] if args.quick else [3, 5, 10, 20, 40, 80, 160]
    reps = 1 if args.quick else args.reps

    # One planted world per rep, reused at every sweep point. Drawing a fresh world per point
    # would make the RMSE-vs-attempts curve partly a plot of world-to-world variation.
    worlds = [make_world(args.puzzles, args.players, random.Random(args.seed + r * 977))
              for r in range(reps)]

    regimes = [("random", False, 0.0), ("banded", True, 0.0)]
    regimes += [(f"banded+{f:.0%} link", True, f) for f in args.linking]
    width = max(len(r[0]) for r in regimes)

    print(f"\n  {args.puzzles} puzzles, {args.players} players, {reps} rep(s) per point, "
          f"band {args.band:.0f}")
    print("  outcome model: logistic on true skill minus true difficulty, 400-point scale")
    print("  RMSE(off) keeps the fitted scale; RMSE(aff) removes it. slope 1.0 == scales agree.\n")
    print(f"  {'attempts':>8}  {'regime':<{width}}  {'RMSE(off)':>9}  {'RMSE(aff)':>9}  "
          f"{'slope':>5}  {'±100':>5}  {'rho':>5}")
    print(f"  {'-'*8}  {'-'*width}  {'-'*9}  {'-'*9}  {'-'*5}  {'-'*5}  {'-'*5}")

    results: dict[str, list[tuple[int, float, float]]] = {r[0]: [] for r in regimes}
    for n in sweep:
        for regime, banded, linking in regimes:
            scores = []
            for r in range(reps):
                rng = random.Random(args.seed + r * 7919 + n)
                pz, _ = simulate(worlds[r], n, banded, rng,
                                 band=args.band, linking=linking)
                scores.append(score(pz, worlds[r].puzzles))
            off, aff = mean([s.rmse_offset for s in scores]), mean([s.rmse_affine for s in scores])
            print(f"  {n:>8}  {regime:<{width}}  {off:>9.1f}  {aff:>9.1f}  "
                  f"{mean([s.slope for s in scores]):>5.2f}  "
                  f"{mean([s.within_100 for s in scores]):>4.0%}  "
                  f"{mean([s.rho for s in scores]):>5.2f}")
            results[regime].append((n, off, aff))
        print()

    _plot(results, args.out, args.puzzles, args.players)


def _plot(results: dict, out: Path, n_puzzles: int, n_players: int) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7.5, 4.6), dpi=160)
    fixed = {"random": ("#2563eb", "o", "random pairing (ungated diagnostic)"),
             "banded": ("#dc2626", "s", "banded pairing (skill-tree gating)")}
    greens = ["#16a34a", "#0d9488", "#4d7c0f", "#065f46"]

    linked = 0
    for regime, pts in results.items():
        if regime in fixed:
            colour, marker, label = fixed[regime]
        else:
            colour, marker, label = greens[linked % len(greens)], "^", regime
            linked += 1
        ax.plot([p[0] for p in pts], [p[1] for p in pts],
                marker=marker, color=colour, lw=2, ms=5, label=label)

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
             f"simulation: {n_puzzles} puzzles, {n_players} players, online Glicko-2 with Lichess "
             f"clamps, scale-preserving RMSE.\nShows what it would take to measure difficulty, "
             f"not that any label is wrong.",
             fontsize=6.5, color="#64748b")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    print(f"  wrote {out}\n")


if __name__ == "__main__":
    main()
