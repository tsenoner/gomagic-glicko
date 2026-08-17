#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy"]
# ///
"""
Is the gating penalty real, or an artefact of using an *online* estimator?

    ./batch_fit.py                 # the comparison
    ./batch_fit.py --quick
    ./batch_fit.py --l2 0.03       # weaken the prior; see the note on shrinkage below

Why this exists
---------------
`recovery.py` runs Glicko-2 sequentially, one attempt at a time, because that is how a live
system works. Sequential estimators are known to do worse than a joint fit on sparsely-linked
data: early updates are made against opponents whose own ratings are still garbage, and that
error never fully washes out.

So a sceptical reader is right to ask whether "skill-tree gating costs you 300 RMSE" is a fact
about *gating* or a fact about *online Glicko*. This settles it by fitting the very same simulated
attempt log jointly, by maximum a posteriori, and comparing.

Both estimators are handed one list of attempts produced by `recovery.make_log` — not two draws
from the same process — so the difference between the columns is the estimator and nothing else.

The model is the one the simulation generates from, so this is the best case a batch fit could
possibly achieve — no model misspecification, only the information actually present in the data.
If a correctly-specified batch fit given perfect model knowledge still cannot recover difficulty
under gating, the limitation is in the data, not the estimator.

The prior is not a free lunch
-----------------------------
This is MAP, not MLE, and it has to be: a player with one attempt is perfectly separated, so the
unregularised likelihood is maximised at infinity. But the strength of that prior sets how much
the fitted scale is compressed, and compression shows up as error under a scale-preserving metric
while being invisible to a scale-free one. So `--l2` defaults to the value implied by the
population the simulation actually draws from, rather than a hand-picked number, and both metrics
are reported side by side with the fitted slope so the compression is visible rather than assumed
away. `--l2` is there to let you check the sensitivity yourself.
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from glicko2 import DEFAULT_RATING, SCALE
from recovery import TRUE_SD, make_log, make_world, replay, score_values

# A Gaussian prior of sd `TRUE_SD` (the sd both planted populations are drawn with), expressed in
# the model's natural-log units, is an L2 weight of 1/sd^2. Deriving it beats picking it: tuning
# the prior against the planted truth would be choosing a knob by peeking at the answer.
DEFAULT_L2 = (SCALE / TRUE_SD) ** 2

# The penalised objective is flat well before this (measured: no change in the fitted values
# between 2,000 and 12,000 iterations at any sweep point), so the extra iterations were waste.
DEFAULT_ITERS = 2000


def fit(log, n_players: int, n_puzzles: int, iters: int = DEFAULT_ITERS,
        lr: float = 0.5, l2: float = DEFAULT_L2) -> tuple[np.ndarray, np.ndarray]:
    """Joint MAP fit for player skills and puzzle difficulties (a Rasch model, fitted by Adam).

    Returns (skills, difficulties) on the Elo scale.
    """
    if not log:
        return np.zeros(n_players), np.zeros(n_puzzles)

    pi = np.array([r[0] for r in log])
    zi = np.array([r[1] for r in log])
    y = np.array([r[2] for r in log])

    theta = np.zeros(n_players)   # skills, natural-log units
    beta = np.zeros(n_puzzles)    # difficulties
    mt = np.zeros_like(theta); vt = np.zeros_like(theta)
    mb = np.zeros_like(beta); vb = np.zeros_like(beta)
    b1, b2, eps = 0.9, 0.999, 1e-8

    for t in range(1, iters + 1):
        z = theta[pi] - beta[zi]
        p = 1.0 / (1.0 + np.exp(-z))
        resid = y - p                                  # dLL/dz

        gt = -np.bincount(pi, weights=resid, minlength=n_players) + l2 * theta
        gb = np.bincount(zi, weights=resid, minlength=n_puzzles) + l2 * beta

        for g, m, v, par in ((gt, mt, vt, theta), (gb, mb, vb, beta)):
            m *= b1; m += (1 - b1) * g
            v *= b2; v += (1 - b2) * g * g
            par -= lr * (m / (1 - b1 ** t)) / (np.sqrt(v / (1 - b2 ** t)) + eps)

        # z = theta - beta has exactly one degeneracy, a common shift, so exactly one constraint
        # is free. Pinning both means would impose two and destroy the identifiable difference
        # between mean skill and mean difficulty; the Rasch convention is to pin the items.
        beta -= beta.mean()

    return theta * SCALE + DEFAULT_RATING, beta * SCALE + DEFAULT_RATING


def mean_of(scores: list, field: str) -> float:
    """Mean of one Score field across reps."""
    return sum(getattr(x, field) for x in scores) / len(scores)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--puzzles", type=int, default=300)
    ap.add_argument("--players", type=int, default=3000)
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--band", type=float, default=300.0)
    ap.add_argument("--l2", type=float, default=DEFAULT_L2,
                    help=f"Gaussian prior weight for the joint fit (default {DEFAULT_L2:.4f}, "
                         "derived from the planted population sd)")
    ap.add_argument("--iters", type=int, default=DEFAULT_ITERS)
    ap.add_argument("--seed", type=int, default=20260816)
    args = ap.parse_args()

    sweep = [10, 40] if args.quick else [10, 40, 160]
    reps = 1 if args.quick else args.reps

    print(f"\n  {args.puzzles} puzzles, {args.players} players — online Glicko-2 vs joint MAP fit")
    print(f"  Both estimators are scored on the same attempt log. prior l2={args.l2:.4f}, "
          f"{args.iters} iters.")
    print("  RMSE(off) keeps the fitted scale; RMSE(aff) removes it. slope 1.0 == scales agree.\n")
    print(f"  {'attempts':>8}  {'regime':<7}  {'estimator':<9}  {'RMSE(off)':>9}  "
          f"{'RMSE(aff)':>9}  {'slope':>5}  {'rho':>5}")
    print(f"  {'-'*8}  {'-'*7}  {'-'*9}  {'-'*9}  {'-'*9}  {'-'*5}  {'-'*5}")

    for n in sweep:
        for banded in (False, True):
            rows = {"online": [], "batch": []}
            for r in range(reps):
                world_rng = random.Random(args.seed + r * 977)
                sim = make_world(args.puzzles, args.players, world_rng)

                # One log, both estimators. This is the whole point of the file.
                log_rng = random.Random(args.seed + r * 7919 + n)
                log = make_log(sim, n, banded, log_rng, band=args.band)

                pz, _ = replay(log, args.players, args.puzzles)
                _, beta = fit(log, args.players, args.puzzles,
                              iters=args.iters, l2=args.l2)

                # Score both on the same subset: the puzzles the log actually touches.
                seen = sorted({zi for _, zi, _ in log})
                truth = [sim.puzzles[i] for i in seen]
                rows["online"].append(score_values([pz[i].rating for i in seen], truth))
                rows["batch"].append(score_values([float(beta[i]) for i in seen], truth))

            for est in ("online", "batch"):
                s = rows[est]
                print(f"  {n:>8}  {'banded' if banded else 'random':<7}  {est:<9}  "
                      f"{mean_of(s, 'rmse_offset'):>9.1f}  {mean_of(s, 'rmse_affine'):>9.1f}  "
                      f"{mean_of(s, 'slope'):>5.2f}  {mean_of(s, 'rho'):>5.2f}")
        print()


if __name__ == "__main__":
    main()
