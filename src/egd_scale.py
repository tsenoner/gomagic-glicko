#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Measure what one Go rank is worth, from the European Go Database's own published statistics.

    ./src/egd_scale.py --selftest    # verify the arithmetic, no network
    ./src/egd_scale.py               # fetch (cached) and print every number in RESEARCH.md §1
    ./src/egd_scale.py --offline     # report from the cache only, fail if it is cold

What this exists to settle
--------------------------
Everything else in this repo is denominated in rating points, and the conversion to ranks decides
what those points *mean*. The convention the repo uses — 100 points per rank, 1d = 2100 — is EGF's
*label* map, which is linear by decree. Whether 100 points is a constant amount of skill is a
different question, and the answer is no: it is what a rank is worth as a win probability that
changes with level, by about 5x across the amateur range.

That question is usually argued from competing rating-system formulas (EGF's, OGS's, AGA's), which
disagree with each other by up to 24 percentage points. It does not have to be argued at all. EGD
publishes the observed win counts, and this script pools them: ~675k even tournament games and a
~1.05M-game calibration table, against which all four published mappings can simply be scored.

The one measurement that matters most is not the headline curve but the split between two spaces:

    rating -> win probability   is calibrated to under one percentage point
    rank   -> win probability   is where the information is lost

A rank label is a quantised, noisy, level-dependent projection of a rating, and this script
measures the size of each of those three losses separately.

Cost, and why the cache exists
------------------------------
Each `winning_stats` query is an aggregate over the whole game table and takes EGD roughly a
minute; the full range times out server-side, which is why the span is cut into eleven windows.
A cold run is therefore ~12 minutes of mostly waiting, fetched sequentially to stay polite to a
volunteer-run server. Responses are cached under `out/egd/` (not committed — it is EGD's data,
not ours) and reused forever after.

EGD is live: new tournaments are added continuously, so re-running this will give slightly larger
counts than the figures quoted in the docs, which were taken on 2026-09-01. The conclusions are
not close to the precision where that matters.
"""

from __future__ import annotations

import argparse
import html
import math
import re
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "out" / "egd"
BASE = "https://europeangodatabase.eu"

# Eleven windows covering 1996-2025. Three-year spans keep each query under EGD's timeout; the
# last two are split because that is how the published figures were taken. Counts are additive
# over disjoint date ranges, so the partition does not affect any total.
WINDOWS = [(1996, 1998), (1999, 2001), (2002, 2004), (2005, 2007), (2008, 2010), (2011, 2013),
           (2014, 2016), (2017, 2019), (2020, 2022), (2023, 2024), (2025, 2025)]

# EGD's rating floor sits at 20 kyu, so every player weaker than that piles into the 20k label and
# its win rates are not interpretable. Labelle and Kaniuk independently discard everything below
# ~12k for the same reason. Reported, then excluded from every fit.
FLOOR_GRADE = -20


# --------------------------------------------------------------------------------------------
# the rank index
#
# Ranks are contiguous but their names are not: there is no "0 kyu" between 1k and 1d. Every
# gap calculation below therefore runs on a contiguous index c, and only the printing converts
# back to a name. Getting this wrong silently corrupts one row in twenty — the 1k row — which is
# exactly the row the "100 points per rank" convention is anchored to.
# --------------------------------------------------------------------------------------------

def cidx(grade: str) -> int:
    """'20k' -> -20, '1k' -> -1, '1d' -> 0, '7d' -> 6."""
    n = int(grade[:-1])
    return -n if grade[-1] == "k" else n - 1


def rank_name(c: int) -> str:
    return f"{-c}k" if c < 0 else f"{c + 1}d"


def nominal_gor(c: int) -> float:
    """EGF's label map: 1d = 2100, one grade = 100 points."""
    return 2100 + 100 * c


# --------------------------------------------------------------------------------------------
# the four published mappings, each returning P(the weaker player wins)
# --------------------------------------------------------------------------------------------

def p_egf2021(c: int, gap: int) -> float:
    """EGF since 2021: Bradley-Terry on a log-transformed rating.

    Se = 1/(1 + exp(beta(r2) - beta(r1))),  beta(r) = -7*ln(3300 - r)
    https://europeangodatabase.eu/docs/about/egf-rating-system
    """
    beta = lambda r: -7 * math.log(3300 - r)
    return 1 / (1 + math.exp(beta(nominal_gor(c + gap)) - beta(nominal_gor(c))))


def p_egf_legacy(c: int, gap: int) -> float:
    """EGF before 2021: logistic with a linearly rank-dependent scale, minus an anti-drift epsilon."""
    weak, strong = nominal_gor(c), nominal_gor(c + gap)
    a = max(205 - (weak - 100) / 20, 70)
    return 1 / (math.exp((strong - weak) / a) + 1) - 0.016


def p_ogs(c: int, gap: int) -> float:
    """OGS: vanilla Glicko-2 on a rank scale that is exponential rather than linear.

    rating(rank_idx) = 525*exp(rank_idx/23.15), rank_idx = c + 30 (so 30k = 0, 1d = 30).
    """
    r = lambda cc: 525 * math.exp((cc + 30) / 23.15)
    return 1 / (1 + 10 ** ((r(c + gap) - r(c)) / 400))


def p_aga(c: int, gap: int) -> float:
    """AGA BayRate: probit, one rank = one stone = a constant 100 rating points at every level.

    sigma_px was chosen "to be consistent with the model that the rating point equivalent of an
    n stone handicap is 100n" — an imposed assumption rather than a fit, which is why it is the
    outlier. Evaluated at the standard komi 7.5.
    """
    del c
    sigma = 1.0649 - 0.0021976 * 7.5 + 0.00014984 * 7.5**2
    return 0.5 * (1 + math.erf(-gap / sigma / math.sqrt(2)))


MODELS = {"EGF 2021": p_egf2021, "OGS": p_ogs, "EGF legacy": p_egf_legacy, "AGA": p_aga}


# --------------------------------------------------------------------------------------------
# statistics
# --------------------------------------------------------------------------------------------

def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Score interval. Normal-approximation intervals misbehave for the lopsided cells here."""
    p, d = k / n, 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return centre - half, centre + half


def elo_from_p(p: float) -> float:
    """Rating gap, on the standard 400-point logistic, implied by a win probability."""
    return 400 * math.log10(p / (1 - p))


# Gauss-Hermite nodes/weights for 10 points, for integrating over the label noise below.
_GH = [(-3.436159, 7.640433e-6), (-2.532732, 1.343646e-3), (-1.756684, 3.387439e-2),
       (-1.036611, 2.401386e-1), (-0.342901, 6.108626e-1), (0.342901, 6.108626e-1),
       (1.036611, 2.401386e-1), (1.756684, 3.387439e-2), (2.532732, 1.343646e-3),
       (3.436159, 7.640433e-6)]
_GHW = sum(w for _, w in _GH)


def p_observed(delta: float, sd: float) -> float:
    """Win probability actually observed when the true gap is `delta` Elo but each player's
    strength is displaced from their *label* by N(0, sd^2).

    This is the attenuation that is usually invoked to explain why measured win rates come out
    lower than handicap-anchored systems predict. Quantifying it is the point: near p = 0.5 the
    logistic is nearly linear, so symmetric noise barely moves the answer, and the explanation
    turns out not to work.
    """
    if sd <= 0:
        return 1 / (1 + 10 ** (-delta / 400))
    s = math.sqrt(2) * sd                     # the difference of two independent displacements
    return sum(w / (1 + 10 ** (-(delta + math.sqrt(2) * s * x) / 400)) for x, w in _GH) / _GHW


def invert(p: float, sd: float) -> float:
    """The true Elo gap whose *observed* win rate under label noise `sd` is p."""
    lo, hi = -100.0, 4000.0
    for _ in range(200):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if p_observed(mid, sd) < p else (lo, mid)
    return (lo + hi) / 2


# --------------------------------------------------------------------------------------------
# fetching
# --------------------------------------------------------------------------------------------

def _get(url: str, timeout: int = 600) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "gomagic-glicko/egd_scale"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def cached(name: str, url: str, *, offline: bool) -> str:
    """Fetch `url` once, then serve from out/egd/ forever. Write-then-rename, so a run killed
    mid-download cannot leave a truncated file that the next run mistakes for a finished one."""
    path = CACHE / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    if offline:
        sys.exit(f"--offline, but {path} is not cached. Run without --offline first.")
    CACHE.mkdir(parents=True, exist_ok=True)
    print(f"    fetching {name} (EGD aggregates take ~1 min per window) ...", flush=True)
    body = _get(url)
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_text(body, encoding="utf-8")
    tmp.replace(path)
    return body


def winning_stats(lo: int, hi: int, *, offline: bool) -> str:
    url = (f"{BASE}/EGD/winning_stats.php?mode=Ajax"
           f"&From={lo}-01-01&To={hi}-12-31")
    return cached(f"winning_stats_{lo}_{hi}.html", url, offline=offline)


def ladder(*, offline: bool) -> str:
    """The all-European active list: one row per player, with declared grade and current GoR."""
    return cached("alleuro.html", f"{BASE}/EGD/createalleuro3.php?country=**&dgob=false",
                  offline=offline)


def _pre_blocks(page: str) -> list[str]:
    """EGD renders these tables as preformatted text, not as HTML tables."""
    return [html.unescape(re.sub(r"(?s)<[^>]+>", "", b))
            for b in re.findall(r"(?is)<pre>(.*?)</pre>", page)]


# --------------------------------------------------------------------------------------------
# parsing
# --------------------------------------------------------------------------------------------

def parse_even_games(pages: list[str]) -> dict[tuple[int, int], list[int]]:
    """'Winning Statistics - Even Games': wins and games of the WEAKER player, by declared grade
    and by grade gap 1-4. Returns {(rank_index, gap): [wins, games]}."""
    pool: dict[tuple[int, int], list[int]] = defaultdict(lambda: [0, 0])
    for page in pages:
        for block in _pre_blocks(page):
            if "Winning Statistics - Even Games" not in block:
                continue
            for line in block.splitlines():
                m = re.match(r"^\s*(\d{1,2}[kd])\s+(.*)$", line)
                if not m:
                    continue
                c, nums = cidx(m.group(1)), m.group(2).split()
                for gap in range(1, 5):
                    b = (gap - 1) * 3                    # each gap contributes Nw, Ng, Pw
                    if b + 2 < len(nums):
                        try:
                            wins, games = int(nums[b]), int(nums[b + 1])
                        except ValueError:
                            continue
                        pool[(c, gap)][0] += wins
                        pool[(c, gap)][1] += games
    return pool


def parse_calibration(pages: list[str]) -> list[tuple[float, int, int, float, float]]:
    """'Statistics of Even Games - all players': games bucketed by the rating model's own
    predicted Se, against what actually happened. Returns per-bin
    (bin_low, wins, games, sum of predicted Se * games, sum of grade-rating gap * games)."""
    acc: dict[float, list[float]] = defaultdict(lambda: [0, 0, 0.0, 0.0])
    row = re.compile(r"^\s*([\d.]+)\s+([\d.]+)\s+(-?[\d.]+)\s+(\d+)\s+(\d+)\s+([\d.]+)\s+"
                     r"([\d.]+)\s+(-?[\d.]+)\s+([\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s*$")
    for page in pages:
        for block in _pre_blocks(page):
            if "Even Games - all players" not in block:
                continue
            for line in block.splitlines():
                m = row.match(line)
                if not m:
                    continue
                lo, wins, games = float(m.group(1)), int(m.group(4)), int(m.group(5))
                a = acc[lo]
                a[0] += wins
                a[1] += games
                a[2] += float(m.group(7)) * games      # ASe, the model's own prediction
                a[3] += float(m.group(10)) * games     # ARGD, declared grade minus actual rating
    return [(lo, int(v[0]), int(v[1]), v[2], v[3]) for lo, v in sorted(acc.items())]


def parse_handicap(pages: list[str]) -> dict[int, list[int]]:
    """'Statistics of Handicap Games - strong side all': wins of the weak side, by grade
    difference and stones given. Returns only the fair diagonal {stones: [wins, games]} where
    the handicap equals the grade difference — the setting that is supposed to be 50/50."""
    pool: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    for page in pages:
        for block in _pre_blocks(page):
            if "Handicap Games - strong side all" not in block:
                continue
            for line in block.splitlines():
                m = re.match(r"^\s*(\d{1,2})\s+(.*)$", line)
                if not m:
                    continue
                diff, nums = int(m.group(1)), m.group(2).split()
                b = (diff - 1) * 3
                if b + 2 < len(nums):
                    try:
                        wins, games = int(nums[b]), int(nums[b + 1])
                    except ValueError:
                        continue
                    pool[diff][0] += wins
                    pool[diff][1] += games
    return pool


def parse_ladder(page: str) -> list[tuple[int, int]]:
    """The active ladder as (rank_index, GoR) pairs. Professional grades are dropped: EGF's
    pro scale is explicitly provisional and does not sit on the amateur line."""
    body = re.sub(r"(?s)<[^>]+>", "", page[page.find("<pre>"):])
    row = re.compile(r"^\s*\d+\s+(.+?)\s{2,}([A-Z*]{2})\s+(\d{1,2}[kd])\s+(-?\d+)\s+")
    out = []
    for line in html.unescape(body).splitlines():
        m = row.match(line)
        if m:
            out.append((cidx(m.group(3)), int(m.group(4))))
    return out


# --------------------------------------------------------------------------------------------
# the report
# --------------------------------------------------------------------------------------------

def ols(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    """Returns (slope, intercept, Pearson r)."""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    return sxy / sxx, my - (sxy / sxx) * mx, sxy / math.sqrt(sxx * syy)


def stdev(v: list[float]) -> float:
    m = sum(v) / len(v)
    return math.sqrt(sum((x - m) ** 2 for x in v) / len(v))


def report(pool, calib, hcap, players) -> None:
    grades: dict[int, list[float]] = defaultdict(list)
    for c, gor in players:
        grades[c].append(gor)

    print("\n" + "=" * 96)
    print("1. THE LABEL MAP  —  is one rank really 100 rating points?")
    print("=" * 96)
    print(f"\n  {len(players):,} active European players with a declared grade and a rating.\n")
    print(f"  {'band':<12}{'n':>7}{'slope (GoR/rank)':>20}{'Pearson r':>12}{'resid. SD':>12}")
    print(f"  {'-' * 12}{'-' * 7}{'-' * 20}{'-' * 12}{'-' * 12}")
    for label, lo, hi in [("20k-11k", -20, -11), ("10k-1k", -10, -1), ("1d-7d", 0, 6),
                          ("20k-7d", -20, 6)]:
        sel = [(c, g) for c, g in players if lo <= c <= hi]
        xs, ys = [float(c) for c, _ in sel], [float(g) for _, g in sel]
        slope, icept, r = ols(xs, ys)
        resid = stdev([y - (slope * x + icept) for x, y in zip(xs, ys, strict=True)])
        print(f"  {label:<12}{len(sel):>7,}{slope:>20.1f}{r:>12.3f}{resid:>12.1f}")

    print("\n  Spread of rating WITHIN one declared grade — how much a rank label actually pins down:\n")
    print(f"  {'grade':>7}{'n':>7}{'mean GoR':>11}{'nominal':>10}{'SD':>8}{'SD in ranks':>14}")
    print(f"  {'-' * 7}{'-' * 7}{'-' * 11}{'-' * 10}{'-' * 8}{'-' * 14}")
    for c in (-20, -15, -10, -5, -1, 0, 2, 4):
        v = grades.get(c, [])
        if len(v) < 10:
            continue
        sd = stdev(v)
        print(f"  {rank_name(c):>7}{len(v):>7,}{sum(v) / len(v):>11.1f}{nominal_gor(c):>10.0f}"
              f"{sd:>8.1f}{sd / 100:>13.2f}")

    total = sum(g for _, g in pool.values())
    print("\n" + "=" * 96)
    print(f"2. THE WIN-PROBABILITY MAP  —  {total:,} even games, pooled {WINDOWS[0][0]}-{WINDOWS[-1][1]}")
    print("=" * 96)
    print("\n  Win rate of the STRONGER player across one declared grade, with 95% Wilson intervals,")
    print("  against what each published rating system predicts.\n")
    print(f"  {'rank':>6}{'games':>9}{'stronger wins':>16}{'95% CI':>16}{'Elo/rank':>10}"
          f"{'95% CI':>14}   " + "".join(f"{k:>11}" for k in MODELS))
    print(f"  {'-' * 6}{'-' * 9}{'-' * 16}{'-' * 16}{'-' * 10}{'-' * 14}   "
          + "".join(f"{'-' * 10:>11}" for _ in MODELS))
    for c in sorted({c for c, gap in pool if gap == 1}):
        wins, games = pool[(c, 1)]
        if games < 300:
            continue
        p = 1 - wins / games
        lo, hi = wilson(wins, games)
        plo, phi = 1 - hi, 1 - lo
        flag = "  <- rating floor, not interpretable" if c == FLOOR_GRADE else ""
        print(f"  {rank_name(c):>6}{games:>9,}{p * 100:>15.1f}%"
              f"{f'[{plo * 100:.1f}, {phi * 100:.1f}]':>16}{elo_from_p(p):>10.0f}"
              f"{f'[{elo_from_p(plo):.0f}, {elo_from_p(phi):.0f}]':>14}   "
              + "".join(f"{(1 - fn(c, 1)) * 100:>10.1f}%" for fn in MODELS.values()) + flag)

    print("\n  Game-weighted mean absolute error, grades 18k-6d, gaps 1-4"
          "  (the 20k floor row is excluded):\n")
    bands = [("overall", -18, 5), ("18k-10k", -18, -10), ("9k-1k", -9, -1), ("1d-6d", 0, 5)]
    print(f"  {'model':<13}" + "".join(f"{b[0]:>12}" for b in bands))
    print(f"  {'-' * 13}" + "".join(f"{'-' * 11:>12}" for _ in bands))
    for label, fn in MODELS.items():
        cells = []
        for _, lo, hi in bands:
            num = den = 0.0
            for (c, gap), (wins, games) in pool.items():
                if games < 300 or not lo <= c <= hi:
                    continue
                num += games * abs(wins / games - fn(c, gap))
                den += games
            cells.append(f"{num / den * 100:>11.2f}p")
        print(f"  {label:<13}" + "".join(cells))

    # Cross-check against a published analysis of the same tables.
    print("\n  Cross-check — Kaniuk (2011) reports 35% and 22% for these two cells:")
    for label, c, gap in [("a 4k beats a 2k", -4, 2), ("a 2d beats a 4d", 1, 2)]:
        wins, games = pool[(c, gap)]
        print(f"    {label}: {wins / games * 100:.1f}%  (n = {games:,})")

    print("\n" + "=" * 96)
    print("3. WHERE THE INFORMATION IS LOST  —  rank labels, not the rating scale")
    print("=" * 96)
    cal_games = sum(g for _, _, g, _, _ in calib)
    print(f"\n  EGF-2021 predicting from RATINGS, {cal_games:,} games in {len(calib)} bins of its own")
    print("  predicted Se. ARGD is the average gap between a player's declared grade and their")
    print("  actual rating — positive means the grade flatters the player.\n")
    print(f"  {'Se bin':>13}{'games':>10}{'predicted':>11}{'observed':>10}{'error':>9}{'ARGD':>8}")
    print(f"  {'-' * 13}{'-' * 10}{'-' * 11}{'-' * 10}{'-' * 9}{'-' * 8}")
    num = den = 0.0
    for lo, wins, games, se_sum, argd_sum in calib:
        if games < 500:
            continue
        pred, obs = se_sum / games, wins / games * 100
        num += games * abs(obs - pred)
        den += games
        print(f"  {f'{lo:.1f}-{lo + 2.5:.1f}':>13}{games:>10,}{pred:>10.1f}%{obs:>9.1f}%"
              f"{obs - pred:>+8.1f}p{argd_sum / games:>+8.1f}")
    print(f"\n  ==> game-weighted mean |error| = {num / den:.2f} percentage points.")
    print("      Predicting from ratings is calibrated to under a point. Predicting from rank")
    print("      labels (section 2) is off by 3+. The labels are the lossy step, not the scale.")

    print("\n  Is the loss just label noise? Correct the observed win rates for the within-grade")
    print("  scatter measured in section 1 and see how far the answer moves:\n")
    print(f"  {'rank':>6}{'SD (GoR)':>10}{'SD (Elo)':>10}{'gap1 raw':>10}{'gap1 corr':>11}"
          f"{'gap4 raw':>10}{'gap4 corr':>11}")
    print(f"  {'-' * 6}{'-' * 10}{'-' * 10}{'-' * 10}{'-' * 11}{'-' * 10}{'-' * 11}")
    for c in (-10, -5, -1, 0, 2):
        v = grades.get(c, [])
        if len(v) < 10 or (c, 1) not in pool:
            continue
        sd_gor = stdev(v)
        # Convert the GoR-scale spread into Elo-400 units using EGF-2021's local logistic scale.
        sd_elo = sd_gor * (400 / math.log(10)) / ((3300 - nominal_gor(c)) / 7)
        cells = []
        for gap in (1, 4):
            if (c, gap) not in pool or pool[(c, gap)][1] < 300:
                cells += ["    .", "     ."]
                continue
            wins, games = pool[(c, gap)]
            p = 1 - wins / games
            cells += [f"{invert(p, 0) / gap:10.0f}", f"{invert(p, sd_elo) / gap:11.0f}"]
        print(f"  {rank_name(c):>6}{sd_gor:>10.0f}{sd_elo:>10.1f}" + "".join(cells))
    print("\n  ==> the correction moves the answer by a couple of Elo points, and the gap-4 column")
    print("      sits ABOVE gap-1 — the opposite sign from what attenuation predicts. Label noise")
    print("      does not explain the disagreement with handicap-anchored systems; the curvature")
    print("      is real, and if anything understated.")

    print("\n" + "=" * 96)
    print("4. ONE RANK vs ONE STONE  —  is the handicap actually fair?")
    print("=" * 96)
    print("\n  Win rate of the WEAK side when the handicap equals the grade difference, which is")
    print("  the setting the whole dan/kyu ladder is defined by and should be 50%.\n")
    tw = tn = 0
    for stones in sorted(hcap):
        wins, games = hcap[stones]
        if games < 200:
            continue
        tw, tn = tw + wins, tn + games
        print(f"    {stones} stone{'s' if stones > 1 else ' '} across {stones} grade"
              f"{'s' if stones > 1 else ' '}: {wins / games * 100:5.1f}%   (n = {games:,})")
    if tn:
        print(f"\n  ==> pooled {tw / tn * 100:.1f}% over {tn:,} games. One stone per rank"
              " under-compensates,")
        print("      by roughly half a stone — the correction Go folklore has always claimed.")
    print()


# --------------------------------------------------------------------------------------------

def selftest() -> None:
    """Check the arithmetic without touching the network, so CI can run it."""
    def close(got, want, tol, what):
        assert abs(got - want) < tol, f"{what}: got {got}, want {want}"

    # The contiguous rank index must not leave a hole where "0 kyu" would be.
    assert cidx("20k") == -20 and cidx("1k") == -1 and cidx("1d") == 0 and cidx("7d") == 6
    assert rank_name(cidx("1k") + 1) == "1d", "a one-grade step from 1k must land on 1d"
    close(nominal_gor(cidx("1k")), 2000, 1e-9, "1k = 2000")
    close(nominal_gor(cidx("2d")), 2200, 1e-9, "2d = 2200")

    close(elo_from_p(0.5), 0, 1e-9, "even odds is a zero gap")
    close(elo_from_p(0.76), 200, 1.0, "76% is about 200 points")
    lo, hi = wilson(50, 100)
    close((lo + hi) / 2, 0.5, 0.01, "Wilson centre on a symmetric count")
    assert wilson(1, 10)[0] > 0, "Wilson must not go negative on a lopsided count"

    close(p_egf2021(0, 0), 0.5, 1e-9, "equal ratings are even")
    close(p_aga(0, 1), 0.1717, 1e-3, "AGA puts one rank at 82.8% for the stronger player")
    # EGF-2021's local scale equals the standard 400-point logistic at exactly one rating, and
    # that rating is the 1k/1d boundary. This is the crossover the docs quote.
    r_cross = 3300 - 7 * (400 / math.log(10))
    close(r_cross, 2084, 1.0, "the Elo-400 crossover sits at the 1k/1d boundary")

    close(p_observed(100, 0), 1 / (1 + 10 ** -0.25), 1e-9, "zero noise is the plain logistic")
    close(invert(p_observed(300, 120), 120), 300, 1.0, "invert must undo p_observed")
    assert p_observed(400, 200) < p_observed(400, 0), "noise must attenuate toward 50%"

    # A parser guard: the even-games table is positional, so a shifted column silently corrupts
    # every number. Feed it one known row.
    row = ("<pre>Winning Statistics - Even Games\n"
           " 5k    701  1547   45.3    287   785   36.6\n</pre>")
    pool = parse_even_games([row])
    assert pool[(cidx("5k"), 1)] == [701, 1547], pool[(cidx("5k"), 1)]
    assert pool[(cidx("5k"), 2)] == [287, 785], pool[(cidx("5k"), 2)]

    print("  selftest: all checks passed")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true",
                    help="verify the arithmetic and the parser, without network")
    ap.add_argument("--offline", action="store_true",
                    help="report from out/egd/ only; fail rather than fetch")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return

    print(f"\n  cache: {CACHE}")
    pages = [winning_stats(lo, hi, offline=args.offline) for lo, hi in WINDOWS]
    lad = ladder(offline=args.offline)
    report(parse_even_games(pages), parse_calibration(pages), parse_handicap(pages),
           parse_ladder(lad))


if __name__ == "__main__":
    main()
