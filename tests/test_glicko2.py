#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# ///
"""The validation the README claims: Glickman's worked example, plus the production clamps.

    ./tests/test_glicko2.py

Stdlib only, no test runner, so it is one command from a fresh clone. Exits non-zero on failure.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from glicko2 import (  # noqa: E402
    MAX_DEVIATION,
    MAX_RATING_DELTA,
    MAX_VOLATILITY,
    MIN_DEVIATION,
    Rating,
    play,
    update,
)

_failures: list[str] = []


def check(name: str, got: float, want: float, tol: float) -> None:
    ok = abs(got - want) <= tol
    print(f"  {'ok  ' if ok else 'FAIL'}  {name:<46} got {got:<14.6f} want {want} +/- {tol}")
    if not ok:
        _failures.append(name)


def check_true(name: str, ok: bool) -> None:
    print(f"  {'ok  ' if ok else 'FAIL'}  {name}")
    if not ok:
        _failures.append(name)


def test_glickman_worked_example() -> None:
    """Glickman, "Example of the Glicko-2 system", section 'Example calculation'.

    A player at 1500/200/0.06 plays three opponents, winning the first and losing the other two.
    The paper prints 1464.06 / 151.52 / 0.05999 and uses tau=0.5.

    The paper rounds its intermediate steps, so it disagrees with an unrounded computation in the
    second decimal of the rating. The tolerances below are that rounding, not slack: a genuine
    error in any of Glickman's steps 3-8 moves these numbers by whole points, not hundredths.
    """
    print("\nGlickman's worked example (tau=0.5):")
    got = update(Rating(1500.0, 200.0, 0.06),
                 [(Rating(1400.0, 30.0), 1.0),
                  (Rating(1550.0, 100.0), 0.0),
                  (Rating(1700.0, 300.0), 0.0)],
                 tau=0.5)
    check("rating", got.rating, 1464.06, 0.02)
    check("rating deviation", got.rd, 151.52, 0.01)
    check("volatility", got.vol, 0.05999, 2e-5)
    check_true("the three games are counted", got.games == 3)


def test_no_games_only_grows_uncertainty() -> None:
    """Glickman step 6 applied to an empty rating period: rating held, RD grows to phi*."""
    print("\nA rating period with no games:")
    before = Rating(1600.0, 100.0, 0.06)
    after = update(before, [])
    check("rating unchanged", after.rating, 1600.0, 0.0)
    check("RD grows to sqrt(phi^2 + sigma^2)",
          after.rd, math.sqrt(before.phi ** 2 + before.vol ** 2) * 173.7178, 0.01)
    check_true("RD respects the ceiling", after.rd <= MAX_DEVIATION)
    check_true("RD respects the floor", after.rd >= MIN_DEVIATION)


def test_saturated_expectation_still_scores_the_game() -> None:
    """A gap wide enough to saturate E() in float64 must not silently discard the result.

    At roughly 6,400 points apart, E rounds to exactly 1.0, so v^-1 = sum g^2 E(1-E) underflows
    to zero while the residual sum g(s-E) does not. Taking the v -> infinity limit of steps 6-7
    keeps the game; returning the input unchanged would lose it.
    """
    print("\nA 6,450-point mismatch (E saturates, v^-1 underflows to 0):")
    before = Rating(7950.0, 350.0, 0.09)
    after = update(before, [(Rating(1500.0, 45.0), 0.0)])
    check_true("the loss moves the rating down", after.rating < before.rating - 1.0)
    check_true("the game is counted", after.games == before.games + 1)
    check_true("a fresh object is returned", after is not before)
    check_true("the delta cap still binds",
               after.rating >= before.rating - MAX_RATING_DELTA - 1e-9)


def test_lichess_clamps() -> None:
    """The production clamps apply on every exit path, not just the main one."""
    print("\nLichess production clamps:")
    # A 6,000-point upset would move the rating much further than 700 points unclamped.
    moved = update(Rating(1500.0, 350.0, 0.09), [(Rating(7500.0, 45.0), 1.0)])
    check_true("single update never moves more than MAX_RATING_DELTA",
               moved.rating - 1500.0 <= MAX_RATING_DELTA + 1e-9)
    check_true("volatility never exceeds MAX_VOLATILITY", moved.vol <= MAX_VOLATILITY + 1e-12)

    # Many games against a well-known equal opponent drive RD down to the floor.
    r = Rating()
    for _ in range(400):
        r = update(r, [(Rating(1500.0, 45.0), 1.0), (Rating(1500.0, 45.0), 0.0)])
    check_true("RD never claims more certainty than MIN_DEVIATION", r.rd >= MIN_DEVIATION - 1e-9)


def test_play_is_mutually_calibrating() -> None:
    """Both competitors update against the other's pre-update state, not sequentially."""
    print("\nplay() symmetry:")
    player, puzzle = Rating(1500.0, 200.0, 0.06), Rating(1500.0, 200.0, 0.06)
    p_after, z_after = play(player, puzzle, solved=True)
    check_true("solver's rating rises", p_after.rating > player.rating)
    check_true("puzzle's rating falls", z_after.rating < puzzle.rating)
    check("equal starting points move symmetrically",
          (p_after.rating - player.rating) + (z_after.rating - puzzle.rating), 0.0, 1e-9)

    print("\nHint damping:")
    half_p, half_z = play(player, puzzle, solved=True, weight=0.5)
    check("weight=0.5 moves the player half as far",
          half_p.rating - player.rating, (p_after.rating - player.rating) * 0.5, 1e-9)
    none_p, _ = play(player, puzzle, solved=True, weight=0.0)
    check("weight=0.0 leaves the rating alone", none_p.rating, player.rating, 1e-12)
    check("weight=0.0 leaves the deviation alone", none_p.rd, player.rd, 1e-12)
    check("weight=0.0 leaves the volatility alone", none_p.vol, player.vol, 1e-12)
    check_true("a damped attempt still counts as a game", none_p.games == 1)


def main() -> int:
    for test in (test_glickman_worked_example,
                 test_no_games_only_grows_uncertainty,
                 test_saturated_expectation_still_scores_the_game,
                 test_lichess_clamps,
                 test_play_is_mutually_calibrating):
        test()
    print()
    if _failures:
        print(f"  {len(_failures)} FAILED: {', '.join(_failures)}\n")
        return 1
    print("  all checks passed\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
