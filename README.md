# gomagic-glicko

[![CI](https://github.com/tsenoner/gomagic-glicko/actions/workflows/ci.yml/badge.svg)](https://github.com/tsenoner/gomagic-glicko/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/downloads/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**How much data does it take to measure a Go puzzle's difficulty, instead of guessing it?**

Go Magic assigns difficulty by hand — a static 11-level table, one judgement per puzzle, across
**10,160 puzzles** (their own counter, August 2026), never revised by the millions of attempts
already in their database. This repo simulates the replacement: a solve treated as a Glicko-2 game
between player and puzzle, scored against a planted ground truth. Recovery error is in rating
points, where **100 ≈ one rank** (measured: exact at 1d, generous below) and
**467 = nothing learned**; 300 puzzles, 3,000 players,
10 planted worlds, 95% CIs.

| attempts/puzzle | random pairing | gated (skill tree) | gated, refit jointly |
| --------------- | -------------- | ------------------ | -------------------- |
| 10              | 249.5 ± 4.8    | 408.2 ± 5.1        | 388.1 ± 5.3          |
| 40              | 166.8 ± 4.1    | 355.2 ± 6.1        | 251.5 ± 7.8          |
| 160             | 106.5 ± 3.4    | 287.1 ± 7.4        | **111.5 ± 4.0**      |

**Gating costs ~2.8×, but most of that is the online estimator rather than the data** — a joint
refit of the identical log recovers it. So for a one-off backfill over an existing log, fit jointly;
keep online Glicko for the live path. Uneven traffic costs as much again and, unlike gating, wrecks
the ordering as well as the scale.

This does not claim their labels are wrong — that needs their attempt log. It answers the question
that comes *before* that one. Nothing here uses private data; only the skill tree is real.

## Docs

- [`docs/METHOD.md`](docs/METHOD.md) — **start here if this is new.** Elo → Glicko-2, the algorithm, the experiment, the results.
- [`docs/FINDINGS.md`](docs/FINDINGS.md) — every result with CIs, the planted scale, the [limitations](docs/FINDINGS.md#limitations), the sourcing audit.
- [`docs/RESEARCH.md`](docs/RESEARCH.md) — the literature behind the open design questions.
- [`docs/PROBLEM-SOURCES.md`](docs/PROBLEM-SOURCES.md) — who already rates Go puzzles by attempts, and the licence audit.
- [`docs/RUNNING.md`](docs/RUNNING.md) — every command, the flags worth knowing, the repo layout.
- [`docs/OPEN-QUESTIONS.md`](docs/OPEN-QUESTIONS.md) — what is done, what is open, and the one-pager it builds to.

## Run it

```sh
./tests/test_glicko2.py                     # validate the estimator (Glickman's worked example)
./src/recovery.py --puzzles 300 --reps 10   # reproduce the gated-vs-random rows
./src/egd_scale.py                          # measure what one Go rank is worth, from 675k EGD games
```

Each script carries a [PEP 723](https://peps.python.org/pep-0723/) header, so `uv` resolves its
dependencies on the spot — **no environment to set up, no checkout needed to run one file.**
