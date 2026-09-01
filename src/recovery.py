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
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from glicko2 import DEFAULT_RATING, Rating, play

# --- The rating scale, and what the planted populations actually span ------------------------
# Rank <-> rating uses the EGF *label* convention: one rank = 100 rating points, 1 dan at 2100,
# so 1k = 2000 and 20k = 100. That map is linear by decree, and it is only a labelling — EGF's
# own win-probability model carries a rank-dependent scale, `a_eff = (3300 - r)/7`, which equals
# the 400-point Elo scale used here only near GoR ~2084, i.e. at the 1k/1d boundary.
#
# So this axis is calibrated at the dan boundary and is optimistic everywhere below it. OGS —
# the one production Go server running Glicko-2 — instead maps rank exponentially,
# `rating = 525 * exp(rank_index / 23.15)`, where a rank is worth ~85 points at 1d but only ~55
# at 10k and ~36 at 20k, and the whole 30k..1d span is ~1400 points rather than 3000. Under that
# map an error of 100 points is about one rank at 1d but nearer *three* ranks at 20k.
#
# Read "±100 points ≈ one rank" accordingly: sound where the tree's third tier lives, and
# generous in its first. Nothing in the estimator depends on any of this — it never sees a rank —
# but every error figure quoted in ranks does. See docs/RESEARCH.md §1.
POINTS_PER_RANK = 100.0
DAN_1 = 2100.0

# Both planted populations are drawn N(DEFAULT_RATING, TRUE_SD), which puts 99.7% of the mass in
#     −3 sd = 100 (20k)      mean = 1500 (6k)      +3 sd = 2900 (9d)
# and the central 95% in 567..2433, i.e. 15k..4d. Stated rather than implied because it sets what
# every RMSE below is relative to: an estimator that guesses the population mean for every puzzle
# scores RMSE == TRUE_SD ≈ 467, so that is the no-information ceiling and 467 is not "bad", it is
# "nothing learned". `describe_scale()` prints this at the top of every run.
#
# Note the mismatch this makes explicit, which is a limitation rather than a bug: Go Magic's tree
# spans 30k–1d, so the planted population is *stronger* than the catalogue at the top — about 10%
# of planted puzzles come out above 1d, harder than any real Go Magic puzzle — and does not reach
# the 30k floor at the bottom. The linear rank map is also least accurate exactly where the tree
# spends most of its nodes.
RANK_SPREAD = 1400.0          # half-width at 3 sd, in rating points
TRUE_SD = RANK_SPREAD / 3.0   # 466.7; the sd both planted populations are drawn with


def as_rank(rating: float) -> str:
    """Render a rating on the kyu/dan scale. Presentation only — the model never sees ranks.

    There is no 0 kyu and no 0 dan: 1d sits one step above 1k, so the two branches meet without a
    gap. `steps` counts ranks below 1d, so 0 -> 1d, 1 -> 1k, -1 -> 2d.
    """
    steps = round((DAN_1 - rating) / POINTS_PER_RANK)
    return f"{steps}k" if steps >= 1 else f"{1 - steps}d"


def describe_scale() -> str:
    """One block, printed by every entry point, so the planted range is never left implicit."""
    lo, hi = DEFAULT_RATING - 3 * TRUE_SD, DEFAULT_RATING + 3 * TRUE_SD
    return (f"  scale: 1 rank = {POINTS_PER_RANK:.0f} pts, 1d = {DAN_1:.0f}. Planted truth ~ "
            f"N({DEFAULT_RATING:.0f}, {TRUE_SD:.0f}) for BOTH puzzles and players.\n"
            f"         99.7% of planted mass in {lo:.0f}..{hi:.0f} "
            f"= {as_rank(lo)}..{as_rank(hi)}, centred {as_rank(DEFAULT_RATING)}.\n"
            f"         Guessing the mean for every puzzle scores RMSE = {TRUE_SD:.0f}; "
            f"that is the no-information ceiling.")

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


def funnel_counts(sim: Sim, attempts_per_puzzle: int, funnel: float) -> list[int]:
    """Attempts per puzzle when traffic decays with difficulty, as tree traffic really does.

    The sweep's default gives every puzzle the *same* number of attempts, which is the one thing a
    prerequisite tree certainly does not do: everybody meets the first node, and only the survivors
    reach the last. So "160 attempts per puzzle" as a flat number describes no real catalogue.

    `funnel` is the ratio of traffic on the hardest puzzle to traffic on the easiest — 1.0 is flat
    (off), 0.02 means the hardest puzzle gets 2% of the easiest one's attempts. Counts are
    renormalised so the *mean* is still `attempts_per_puzzle`, which keeps the sweep's x-axis
    meaning "attempts per puzzle on average" and isolates the effect of the shape from the effect
    of the total volume.

    The renormalisation is exact only up to the floor: below roughly 5 mean attempts the floor
    binds on much of the tail and inflates the funnelled total (funnel 0.02 at mean 3: +5.3%),
    so matched-volume comparisons at very low means overstate the funnelled arm's traffic. The
    published points (mean 40 and 160) are floor-free to within rounding.
    """
    n = len(sim.puzzles)
    if funnel >= 1.0 or n < 2:
        return [attempts_per_puzzle] * n
    order = sorted(range(n), key=lambda i: sim.puzzles[i])
    quantile = [0.0] * n
    for pos, i in enumerate(order):
        quantile[i] = pos / (n - 1)
    w = [funnel ** q for q in quantile]
    scale = sum(w) / n
    # Floor of 1: a puzzle with zero attempts is dropped by `score()` rather than measured badly,
    # which would quietly shrink the population being scored instead of showing the cost.
    return [max(1, round(attempts_per_puzzle * wi / scale)) for wi in w]


def make_log(sim: Sim, attempts_per_puzzle: int, banded: bool, rng: random.Random,
             band: float = 300.0, linking: float = 0.0,
             funnel: float = 1.0) -> list[Attempt]:
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

    `funnel` makes the per-puzzle attempt count decay with difficulty instead of being flat; see
    `funnel_counts`. Left at 1.0 the generator is exactly as it was.
    """
    everyone = range(len(sim.players))
    counts = funnel_counts(sim, attempts_per_puzzle, funnel)
    pairs: list[tuple[int, int]] = []
    fallback_puzzles = fallback_attempts = 0
    for zi, zdiff in enumerate(sim.puzzles):
        want = counts[zi]
        # Drawn unconditionally, so the coin sequence cannot depend on the regime — which is what
        # makes linking=1.0 reproduce the random regime draw for draw. (The arms still diverge in
        # later stream consumption — different pools, different sample sizes — so pairing across
        # regimes rests on the shared planted world, not on aligned streams.)
        ungated = rng.random() < linking
        if banded and not ungated:
            pool = [i for i, s in enumerate(sim.players) if abs(s - zdiff) <= band]
            if len(pool) < want:
                pool = sorted(everyone, key=lambda i: abs(sim.players[i] - zdiff))[:want]
                fallback_puzzles += 1
                fallback_attempts += want
        else:
            pool = everyone
        pairs.extend((pi, zi) for pi in rng.sample(pool, min(want, len(pool))))

    # The fallback keeps attempt counts equal across regimes, but each firing hands a puzzle
    # players from across the whole range — the wide comparisons gating denies. In the published
    # *flat* sweeps it fires on <2% of puzzles; past that the "gated" regime quietly stops being
    # gated (16% at 640 attempts, most of the log at 1,280 — see docs/METHOD.md §7). Under
    # --funnel it is worse than the puzzle count suggests, because the head puzzles it fires on
    # carry the most traffic (funnel 0.02 at mean 160: 6% of puzzles but ~21% of attempts), so
    # the rate that matters — and the one warned on — is the attempt share.
    share = fallback_attempts / len(pairs) if pairs else 0.0
    if share > 0.05:
        print(f"  warning: the ±{band:.0f} band could not fill {fallback_puzzles / len(sim.puzzles):.0%} "
              f"of puzzles, and their nearest-N fallback carries {share:.0%} of all attempts — "
              f"this 'gated' log is partly ungated. Scale --players up.",
              file=sys.stderr)

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
             band: float = 300.0, linking: float = 0.0,
             funnel: float = 1.0) -> tuple[list[Rating], list[Rating]]:
    """Build a log and fit it online. The two halves are separate so `batch_fit` can share one."""
    log = make_log(sim, attempts_per_puzzle, banded, rng,
                   band=band, linking=linking, funnel=funnel)
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


# Two-sided t critical values at 95%, indexed by degrees of freedom. Hardcoded because the whole
# repo is stdlib-only and `statistics` has no inverse-t; beyond 30 df, 1.96 + 2.4/df tracks the
# true value within 0.2% (the bare normal 1.96 would run ~4% anticonservative at 31 df and stay
# more than 2% off until ~60).
_T975 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306,
         9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131,
         16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086, 21: 2.080, 22: 2.074,
         23: 2.069, 24: 2.064, 25: 2.060, 26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045,
         30: 2.042}


def ci95(xs: list[float]) -> tuple[float, float]:
    """Mean and the half-width of its 95% t interval. Half-width is nan below two samples."""
    n = len(xs)
    if n < 2:
        return (mean(xs) if n else float("nan")), float("nan")
    t = _T975.get(n - 1, 1.96 + 2.4 / (n - 1))
    return mean(xs), t * statistics.stdev(xs) / math.sqrt(n)


def paired_ci95(a: list[float], b: list[float]) -> tuple[float, float]:
    """95% interval on the mean of `a - b`, elementwise.

    The reps are paired by construction — every arm at a given sweep point runs on the same
    planted world, from an identically seeded log stream — so this is the *correct* interval for
    a contrast, and the per-arm intervals are not. It is not always the *tighter* one: that
    depends on how correlated the two arms are across worlds, and the measured magnitudes at the
    published defaults are in docs/METHOD.md §5. Use it because it is right, not because it is
    always tighter.
    """
    return ci95([x - y for x, y in zip(a, b, strict=True)])


def contrast_str(a: list[float], b: list[float]) -> str:
    """The paired contrast `a − b`, formatted with its significance verdict.

    One home for the decision rule (significant iff the interval excludes zero), so the two
    scripts that print contrasts cannot drift on it.
    """
    d, h = paired_ci95(a, b)
    return f"{d:+.1f} ± {h:.1f}  ({'significant' if abs(d) > h else 'NOT significant'})"


def world_rng(seed: int, rep: int) -> random.Random:
    """The rng stream that plants rep `rep`'s world."""
    return random.Random(seed + rep * 977)


def log_rng(seed: int, rep: int, n: int) -> random.Random:
    """The rng stream that builds rep `rep`'s log at `n` attempts per puzzle.

    Both derivations live here and are imported by `batch_fit`, because "the online rows are the
    same runs, digit for digit" holds only while the two scripts draw identical streams — a
    property better enforced by shared code than by two files keeping their arithmetic in sync.
    """
    return random.Random(seed + rep * 7919 + n)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--puzzles", type=int, default=400)
    ap.add_argument("--players", type=int, default=3000)
    ap.add_argument("--reps", type=int, default=10,
                    help="repeats per point. Every figure is a mean over reps with a 95%% "
                         "t interval; below 2 the interval is undefined")
    ap.add_argument("--quick", action="store_true", help="one rep, fewer sample sizes")
    ap.add_argument("--band", type=float, default=300.0,
                    help="gating width: a player only meets puzzles within this many points")
    ap.add_argument("--linking", type=float, nargs="+", default=[0.10],
                    help="ungated fractions to sweep alongside the pure regimes")
    ap.add_argument("--funnel", type=float, default=1.0,
                    help="traffic on the hardest puzzle as a fraction of the easiest. 1.0 (the "
                         "default) is flat; 0.02 models a prerequisite tree's drop-off. Below "
                         "1.0 the flat twin of every regime runs too, so the paired "
                         "funnel-vs-flat cost is printed rather than left to hand arithmetic")
    ap.add_argument("--sweep", type=int, nargs="+", default=None,
                    help="attempts-per-puzzle points to run. Past ~160 at 3000 players the band "
                         "cannot fill the request and make_log's nearest-N fallback silently "
                         "ungates the sim — scale --players with it or the regime stops being gated")
    ap.add_argument("--seed", type=int, default=20260816)
    ap.add_argument("--out", type=Path, default=Path("out/recovery.png"))
    args = ap.parse_args()

    if not 0.0 < args.funnel <= 1.0:
        ap.error(f"--funnel must be in (0, 1]; got {args.funnel:g}. It is the hardest puzzle's "
                 "share of the easiest one's traffic, and 0 or a negative share is not a shape.")

    sweep = args.sweep if args.sweep is not None else (
        [5, 10, 20, 40] if args.quick else [3, 5, 10, 20, 40, 80, 160])
    reps = 1 if args.quick else args.reps

    # One planted world per rep, reused at every sweep point. Drawing a fresh world per point
    # would make the RMSE-vs-attempts curve partly a plot of world-to-world variation.
    worlds = [make_world(args.puzzles, args.players, world_rng(args.seed, r))
              for r in range(reps)]

    regimes = [("random", False, 0.0), ("banded", True, 0.0)]
    regimes += [(f"banded+{f:.0%} link", True, f) for f in args.linking]
    names = [r[0] for r in regimes]
    if len(set(names)) != len(names):
        # Names key both the results and the printed contrasts; a collision would silently
        # interleave two regimes into one plotted curve.
        ap.error("two --linking fractions round to the same percent label; use distinct values")
    width = max(len(nm) for nm in names)

    print(f"\n  {args.puzzles} puzzles, {args.players} players, {reps} rep(s) per point, "
          f"band {args.band:.0f}"
          + (f", funnel {args.funnel:g}" if args.funnel < 1.0 else ""))
    print(describe_scale())
    print("  outcome model: logistic on true skill minus true difficulty, 400-point scale")
    print("  RMSE(off) keeps the fitted scale; RMSE(aff) removes it. slope 1.0 == scales agree.")
    print("  ± is the half-width of a 95% t interval over reps.\n")
    print(f"  {'attempts':>8}  {'regime':<{width}}  {'RMSE(off)':>17}  {'RMSE(aff)':>9}  "
          f"{'slope':>5}  {'±100':>5}  {'rho':>5}")
    print(f"  {'-'*8}  {'-'*width}  {'-'*17}  {'-'*9}  {'-'*5}  {'-'*5}  {'-'*5}")

    results: dict[str, list[tuple[int, float, float]]] = {nm: [] for nm in names}
    for n in sweep:
        per_regime: dict[str, list[float]] = {}
        flat_twin: dict[str, list[float]] = {}
        for regime, banded, linking in regimes:
            scores = []
            for r in range(reps):
                pz, _ = simulate(worlds[r], n, banded, log_rng(args.seed, r, n), band=args.band,
                                 linking=linking, funnel=args.funnel)
                scores.append(score(pz, worlds[r].puzzles))
            if args.funnel < 1.0 and reps >= 2:
                # The flat twin: the same regime, worlds and log stream at funnel 1.0, so the
                # funnel-vs-flat cost printed below is a paired contrast this one command
                # reproduces (the twin's rows equal the flat sweep's, digit for digit).
                flat_twin[regime] = [
                    score(simulate(worlds[r], n, banded, log_rng(args.seed, r, n),
                                   band=args.band, linking=linking, funnel=1.0)[0],
                          worlds[r].puzzles).rmse_offset
                    for r in range(reps)]
            offs = [s.rmse_offset for s in scores]
            per_regime[regime] = offs
            off, half = ci95(offs)
            cell = f"{off:>9.1f} ± {half:>5.1f}" if half == half else f"{off:.1f}"
            print(f"  {n:>8}  {regime:<{width}}  {cell:>17}  "
                  f"{mean([s.rmse_affine for s in scores]):>9.1f}  "
                  f"{mean([s.slope for s in scores]):>5.2f}  "
                  f"{mean([s.within_100 for s in scores]):>4.0%}  "
                  f"{mean([s.rho for s in scores]):>5.2f}")
            results[regime].append((n, off, half))

        # Paired contrasts. These, not the per-regime intervals above, are what the claims rest on:
        # the regimes share a world and an rng stream, so the difference is far better resolved
        # than either mean. Reported only where a contrast has a defined interval.
        if reps >= 2:
            random_nm, banded_nm, *link_nms = names
            contrasts = [(banded_nm, random_nm)] + [(nm, banded_nm) for nm in link_nms]
            for a, b in contrasts:
                print(f"  {'':>8}  paired {a} − {b}: "
                      f"{contrast_str(per_regime[a], per_regime[b])}")
            for regime, flat_offs in flat_twin.items():
                print(f"  {'':>8}  paired {regime} funnel − flat: "
                      f"{contrast_str(per_regime[regime], flat_offs)}")
        print()

    _plot(results, args.out, args.puzzles, args.players, reps, args.funnel)


def _legend(regime: str) -> str:
    """Curves carry the ungated/gated vocabulary the write-ups use; the printed tables keep the
    internal regime names, so `banded+10% link` reads as `gated + 10% ungated` on the figure."""
    return regime.replace("banded+", "gated + ").replace(" link", " ungated")


def _plot(results: dict, out: Path, n_puzzles: int, n_players: int,
          reps: int, funnel: float) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import NullLocator

    fig, ax = plt.subplots(figsize=(7.5, 5.6), dpi=160)
    fixed = {"random": ("#2563eb", "o", "ungated (random pairing)"),
             "banded": ("#dc2626", "s", "gated (skill tree)")}
    greens = ["#16a34a", "#0d9488", "#4d7c0f", "#065f46"]

    linked = 0
    for regime, pts in results.items():
        if regime in fixed:
            colour, marker, label = fixed[regime]
        else:
            colour, marker, label = greens[linked % len(greens)], "^", _legend(regime)
            linked += 1
        xs, ys, halves = [p[0] for p in pts], [p[1] for p in pts], [p[2] for p in pts]
        ax.plot(xs, ys, marker=marker, color=colour, lw=2, ms=5, label=label)
        # The band is the 95% interval on each regime's own mean. It is not the interval for the
        # gap between two regimes — that one is paired, printed rather than drawn, and not
        # reliably narrower than these bands suggest (see `paired_ci95`). Overlapping bands here
        # therefore do not imply a non-significant difference.
        if reps >= 2:                            # below that the half-widths are nan
            ax.fill_between(xs, [y - h for y, h in zip(ys, halves, strict=True)],
                            [y + h for y, h in zip(ys, halves, strict=True)],
                            color=colour, alpha=0.15, lw=0)

    ax.set_xscale("log")
    # Label the sweep points themselves: the text cites 10, 40 and 160 attempts, and decade ticks
    # alone leave the reader interpolating on a log axis.
    ticks = sorted({x for pts in results.values() for x, *_ in pts})
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{t:g}" for t in ticks])
    ax.xaxis.set_minor_locator(NullLocator())
    # Type sizes are set for the one-pager, where the figure is reproduced at about half its
    # nominal width: matplotlib's 10pt defaults land near 5pt on the printed page.
    ax.set_xlabel("first attempts per puzzle", fontsize=11)
    ax.set_ylabel("difficulty recovery error (RMSE, rating points)", fontsize=11)
    ax.tick_params(labelsize=10)
    ax.set_title("How much data before a puzzle's difficulty is measured?", loc="left", fontsize=12)
    ax.axhline(100, color="#64748b", ls=":", lw=1)
    ax.text(ax.get_xlim()[0] * 1.05, 104, "±100 points ≈ one Go rank", fontsize=9, color="#64748b")
    ax.grid(alpha=0.25, which="both")
    ax.legend(frameon=False, fontsize=10.5)
    ax.spines[["top", "right"]].set_visible(False)
    fig.text(0.01, 0.01,
             f"simulation: {n_puzzles} puzzles, {n_players} players, {reps} reps"
             + (f", funnel {funnel:g}" if funnel < 1.0 else "")
             + f"; planted truth ~ N({DEFAULT_RATING:.0f}, {TRUE_SD:.0f}) "
             f"≈ {as_rank(DEFAULT_RATING - 3 * TRUE_SD)}–{as_rank(DEFAULT_RATING + 3 * TRUE_SD)} "
             f"at ±3 sd.\nOnline Glicko-2 with Lichess clamps. Error is RMSE after removing a "
             f"mean offset, so compression counts; bands are 95% t intervals."
             f"\nShows what measuring difficulty would take, not that any label is wrong.",
             fontsize=7, color="#64748b")
    fig.tight_layout(rect=(0, 0.055, 1, 1))
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    print(f"  wrote {out}\n")


if __name__ == "__main__":
    main()
