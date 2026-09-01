"""
Glicko-2, as Glickman specifies it, plus the production details Lichess added.

Reference: Mark E. Glickman, "Example of the Glicko-2 system" (glicko.net/glicko/glicko2.pdf).

The Lichess-specific parts are noted where they appear. They come from two repositories, not one:
the clamps below are lila's `modules/rating/src/main/Glicko.scala`, while the Glicko-2 arithmetic
Lichess actually runs lives in the separate `scalachess` library as `chess.rating.glicko` — which
is where TAU's 0.75 comes from (`Tau.default`, which lila accepts by not overriding it).
See docs/METHOD.md section 4 for the line-by-line citations and the three places this file
deliberately or accidentally diverges.

The idea being implemented
--------------------------
A puzzle attempt is a *game*: the player is one competitor, the puzzle is the other. Solve it and
the player "wins"; fail and the puzzle "wins". Run that over an attempt log and you get a rating
for every player and every puzzle on one scale, from data you already have.

Go Magic assigns puzzle difficulty by hand — one person's judgement per puzzle, across 10,160 of
them, never revised by the attempts already in the database. This is the machinery that would
turn those judgements into measurements.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Glicko-2's internal scale factor. Glickman writes it as the constant 173.7178; it is exactly
# the Elo 400-point scale in natural-log units, which is why `batch_fit` imports this rather
# than recomputing 400/ln(10) as if it were a different number.
SCALE = 400.0 / math.log(10.0)
DEFAULT_RATING = 1500.0
DEFAULT_RD = 350.0
DEFAULT_VOL = 0.09
TAU = 0.75                # system constant: how fast volatility moves. Glickman suggests 0.3–1.2
EPSILON = 1e-6            # convergence tolerance for the volatility solver

# --- Lichess production clamps (lila: modules/rating/src/main/Glicko.scala) ---------------
MIN_DEVIATION = 45.0      # a rating never claims to be more certain than this  (:46)
MAX_DEVIATION = 500.0     # (:49) — and lila starts competitors here, not at DEFAULT_RD
MAX_VOLATILITY = 0.1      # (:52)
MAX_RATING_DELTA = 700.0  # a single game can never move a rating further than this  (:69)
# Not mirrored here: lila also clamps the rating itself to [400, 4000], which caps the widest
# reachable gap at 3,600 points and so makes the saturation branch in `update` unreachable.


@dataclass
class Rating:
    """A player or a puzzle. Same type on purpose: to the algorithm they are both competitors."""
    rating: float = DEFAULT_RATING
    rd: float = DEFAULT_RD
    vol: float = DEFAULT_VOL
    games: int = 0

    # Glicko-2 works on a transformed scale; convert at the boundary only.
    @property
    def mu(self) -> float:
        return (self.rating - DEFAULT_RATING) / SCALE

    @property
    def phi(self) -> float:
        return self.rd / SCALE


def _g(phi: float) -> float:
    """Weight an opponent's contribution by how well-known their rating is."""
    return 1.0 / math.sqrt(1.0 + 3.0 * phi * phi / (math.pi * math.pi))


def _expected(mu: float, mu_j: float, g_j: float) -> float:
    """Probability that the competitor at `mu` beats the one at `mu_j`, whose weight is `g_j`."""
    return 1.0 / (1.0 + math.exp(-g_j * (mu - mu_j)))


def _clamped(rating: float, rd: float, vol: float, games: int, prev_rating: float) -> Rating:
    """The single exit from `update`, so the Lichess clamps apply to every path identically.

    They used to be open-coded per branch, which meant each of update()'s exits enforced a
    different subset of them.
    """
    return Rating(
        max(prev_rating - MAX_RATING_DELTA, min(prev_rating + MAX_RATING_DELTA, rating)),
        min(max(rd, MIN_DEVIATION), MAX_DEVIATION),
        min(vol, MAX_VOLATILITY),
        games,
    )


def _new_volatility(phi: float, v: float, delta: float, sigma: float, tau: float = TAU) -> float:
    """Glickman's Illinois-variant root finder for the new volatility.

    This is the fiddly part of Glicko-2 and the part most re-implementations get subtly wrong,
    so it follows the paper step by step rather than being 'simplified'.
    """
    a = math.log(sigma * sigma)
    delta_sq, phi_sq = delta * delta, phi * phi

    def f(x: float) -> float:
        ex = math.exp(x)
        num = ex * (delta_sq - phi_sq - v - ex)
        den = 2.0 * (phi_sq + v + ex) ** 2
        return num / den - (x - a) / (tau * tau)

    A = a
    if delta_sq > phi_sq + v:
        B = math.log(delta_sq - phi_sq - v)
    else:
        k = 1
        while f(a - k * tau) < 0:
            k += 1
            if k > 100:                      # pathological input; fail loudly rather than hang
                raise RuntimeError("volatility solver failed to bracket a root")
        B = a - k * tau

    fA, fB = f(A), f(B)
    for _ in range(100):
        if abs(B - A) <= EPSILON:
            break
        C = A + (A - B) * fA / (fB - fA)
        fC = f(C)
        if fC * fB <= 0:
            A, fA = B, fB
        else:
            fA /= 2.0
        B, fB = C, fC

    return math.exp(A / 2.0)


def update(player: Rating, opponents: list[tuple[Rating, float]], tau: float = TAU) -> Rating:
    """Return the player's rating after a rating period.

    `opponents` is [(opponent, score)] with score 1.0 for a win, 0.0 for a loss. Glicko-2 is
    defined over a *period* of games, not a single game; passing one pair is legal and is what
    an online update does.
    """
    phi = player.phi
    if not opponents:
        # No games: only uncertainty grows.
        phi_star = math.sqrt(phi ** 2 + player.vol ** 2)
        return _clamped(player.rating, phi_star * SCALE, player.vol,
                        player.games, player.rating)

    mu = player.mu
    v_inv = 0.0
    delta_sum = 0.0
    for opp, score in opponents:
        g = _g(opp.phi)
        e = _expected(mu, opp.mu, g)
        v_inv += g * g * e * (1.0 - e)
        delta_sum += g * (score - e)

    if v_inv <= 0.0:
        # Every opponent's E saturated to 0 or 1 in float64, so v -> infinity. Steps 6-7 still
        # have a limit there — phi' -> phi_star and mu' = mu + phi_star^2 * delta_sum — and
        # delta_sum is *not* zero, so taking the limit keeps the game instead of discarding it.
        # (Reachable at roughly 6,400 points of rating gap, where exp() saturates.)
        phi_star = math.sqrt(phi ** 2 + player.vol ** 2)
        mu_prime = mu + phi_star * phi_star * delta_sum
        return _clamped(mu_prime * SCALE + DEFAULT_RATING, phi_star * SCALE,
                        player.vol, player.games + len(opponents), player.rating)

    v = 1.0 / v_inv
    delta = v * delta_sum

    sigma_prime = min(_new_volatility(phi, v, delta, player.vol, tau), MAX_VOLATILITY)
    phi_star = math.sqrt(phi ** 2 + sigma_prime ** 2)
    phi_prime = 1.0 / math.sqrt(1.0 / (phi_star * phi_star) + 1.0 / v)
    mu_prime = mu + phi_prime * phi_prime * delta_sum

    return _clamped(mu_prime * SCALE + DEFAULT_RATING, phi_prime * SCALE,
                    sigma_prime, player.games + len(opponents), player.rating)


def play(player: Rating, puzzle: Rating, solved: bool,
         weight: float = 1.0, tau: float = TAU) -> tuple[Rating, Rating]:
    """One attempt. Returns the updated (player, puzzle).

    Both are updated against the other's *pre-update* state, which is what makes the two ratings
    mutually calibrating rather than one chasing the other.

    `weight` is Lichess's damping for attempts where the presentation gives something away. In a
    skill tree you always clicked "Nakade Shapes" before seeing the problem, so the whole tree is
    a hinting context and should be damped; a blind diagnostic test is not. Ignoring this makes
    tree-derived and test-derived ratings disagree with no way to tell which to trust.
    """
    p_before, z_before = player, puzzle
    p_score = 1.0 if solved else 0.0

    new_player = update(p_before, [(z_before, p_score)], tau)
    new_puzzle = update(z_before, [(p_before, 1.0 - p_score)], tau)

    if weight != 1.0:
        new_player = _lerp(p_before, new_player, weight)
        new_puzzle = _lerp(z_before, new_puzzle, weight)
    return new_player, new_puzzle


def _lerp(before: Rating, after: Rating, w: float) -> Rating:
    """Apply only `w` of an update. Used for damped (hinted) attempts.

    Every rated component is damped, volatility included — passing volatility through at full
    strength would let a `weight=0.0` attempt move the rating's uncertainty anyway. The game
    still counts, so `games` comes from `after`.
    """
    return Rating(
        before.rating + (after.rating - before.rating) * w,
        before.rd + (after.rd - before.rd) * w,
        before.vol + (after.vol - before.vol) * w,
        after.games,
    )
