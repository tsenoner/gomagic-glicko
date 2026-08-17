#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy"]
# ///
"""
Is the gating penalty real, or an artefact of using an *online* estimator?

    ./batch_fit.py                 # the comparison
    ./batch_fit.py --quick

Why this exists
---------------
`recovery.py` runs Glicko-2 sequentially, one attempt at a time, because that is how a live
system works. Sequential estimators are known to do worse than a joint fit on sparsely-linked
data: early updates are made against opponents whose own ratings are still garbage, and that
error never fully washes out.

So a sceptical reader is right to ask whether "skill-tree gating plateaus around 300 RMSE" is a
fact about *gating* or a fact about *online Glicko*. This settles it by fitting the same
simulated attempt logs jointly, by maximum likelihood, and comparing.

The model is the one the simulation generates from, so this is the best case a batch fit could
possibly achieve — no model misspecification, only the information actually present in the data.
If a correctly-specified batch fit given perfect model knowledge still cannot recover difficulty
under gating, the limitation is in the data, not the estimator.
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from recovery import make_world, simulate, score, solves  # noqa: E402
from glicko2 import DEFAULT_RATING, Rating  # noqa: E402

SCALE = 400.0 / np.log(10.0)   # Elo 400-point scale, in natural-log units


def build_log(sim, attempts_per_puzzle: int, banded: bool, rng: random.Random,
              band: float = 300.0, linking: float = 0.0):
    """Same attempt-generating process as recovery.simulate, but returns the raw log."""
    rows = []
    for zi, zdiff in enumerate(sim.puzzles):
        use_band = banded and rng.random() >= linking
        if use_band:
            pool = [i for i, s in enumerate(sim.players) if abs(s - zdiff) <= band]
            if len(pool) < attempts_per_puzzle:
                pool = sorted(range(len(sim.players)),
                              key=lambda i: abs(sim.players[i] - zdiff))[:attempts_per_puzzle]
        else:
            pool = range(len(sim.players))
        for pi in rng.sample(list(pool), min(attempts_per_puzzle, len(pool))):
            rows.append((pi, zi, 1.0 if solves(sim.players[pi], sim.puzzles[zi], rng) else 0.0))
    return rows


def fit(log, n_players: int, n_puzzles: int, iters: int = 4000, lr: float = 0.5,
        l2: float = 0.30) -> tuple[np.ndarray, np.ndarray]:
    """Joint MAP fit for player skills and puzzle difficulties (a Rasch model, fitted by Adam).

    Returns (skills, difficulties) on the Elo scale.

    `l2` is a Gaussian prior, not a nuisance knob. Without it this is unusable here: a player
    with one attempt is perfectly separated (all-win or all-loss), the likelihood is maximised at
    infinity, and the fit diverges. At 10 attempts per puzzle most simulated players have one or
    two attempts, so that is the common case, not an edge case. Shrinkage is the standard
    treatment and it is why this is MAP rather than MLE.
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

        # The model is only identified up to a shift; pin the mean each step.
        theta -= theta.mean()
        beta -= beta.mean()

    return theta * SCALE + DEFAULT_RATING, beta * SCALE + DEFAULT_RATING


def affine_score(fitted: list[float], truth: list[float]) -> tuple[float, float]:
    """RMSE after least-squares affine alignment, plus Spearman rho.

    Neither estimator fixes an origin, and a shrunk MAP fit also compresses the scale. Since a
    difficulty label can be rescaled after the fact, the fair question is how much *information*
    each estimator extracted, which is what remains once an affine map is allowed. Applied
    identically to both so the comparison is like for like.
    """
    from recovery import spearman
    f = np.asarray(fitted, dtype=float); t = np.asarray(truth, dtype=float)
    A = np.vstack([f, np.ones_like(f)]).T
    slope, intercept = np.linalg.lstsq(A, t, rcond=None)[0]
    resid = (slope * f + intercept) - t
    return float(np.sqrt((resid ** 2).mean())), spearman(list(f), list(t))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--puzzles", type=int, default=300)
    ap.add_argument("--players", type=int, default=3000)
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--seed", type=int, default=20260816)
    args = ap.parse_args()

    sweep = [10, 40] if args.quick else [10, 40, 160]
    reps = 1 if args.quick else args.reps

    print(f"\n  {args.puzzles} puzzles, {args.players} players — online Glicko-2 vs joint MLE")
    print(f"  Both see the identical attempt log. RMSE after affine alignment, applied to both.\n")
    print(f"  {'attempts':>8}  {'regime':<7}  {'online RMSE':>11}  {'batch RMSE':>10}  "
          f"{'online rho':>10}  {'batch rho':>9}")
    print(f"  {'-'*8}  {'-'*7}  {'-'*11}  {'-'*10}  {'-'*10}  {'-'*9}")

    for n in sweep:
        for banded in (False, True):
            regime = "banded" if banded else "random"
            on_r, ba_r, on_h, ba_h = [], [], [], []
            for r in range(reps):
                seed = args.seed + r * 977 + n
                # Online path
                rng = random.Random(seed)
                sim = make_world(args.puzzles, args.players, rng)
                pz, _ = simulate(sim, n, banded, rng)
                rmse_o, rho_o = affine_score([r.rating for r in pz], sim.puzzles)
                # Batch path, same world and same generating process
                rng2 = random.Random(seed)
                sim2 = make_world(args.puzzles, args.players, rng2)
                log = build_log(sim2, n, banded, rng2)
                _, beta = fit(log, args.players, args.puzzles)
                rmse_b, rho_b = affine_score(list(beta), sim2.puzzles)
                on_r.append(rmse_o); ba_r.append(rmse_b); on_h.append(rho_o); ba_h.append(rho_b)

            f = lambda xs: sum(xs) / len(xs)
            print(f"  {n:>8}  {regime:<7}  {f(on_r):>11.1f}  {f(ba_r):>10.1f}  "
                  f"{f(on_h):>10.2f}  {f(ba_h):>9.2f}")
    print()


if __name__ == "__main__":
    main()
