# gomagic-glicko

**How much data does it take to measure a Go puzzle's difficulty, instead of guessing it?**

Go Magic assigns puzzle difficulty by hand: a static 11-level table, one person's judgement per
puzzle, across **10,160 puzzles**, never revised by the millions of attempts already in their
database. This repo asks what it would take to replace that judgement with a measurement, and
finds one structural obstacle that more data does not fix.

Nothing here uses private data. The skill-tree structure is parsed from a public page; everything
else is simulated.

---

## What this does not claim

**It does not claim their difficulty labels are wrong.** Nobody outside the company can know
that; it needs their attempt log. This answers the question that comes *before* that one: if you
ran the estimator, how much data would you need before the answer meant anything?

That is a property of the estimator and the shape of the data, and it can be settled by
simulation.

---

## Findings

### 1. Their Skill Tree, from the public page

`src/parse_tree.py` reads the `data-*` attributes on `gomagic.org/go-problems/`:

| | |
|---|---|
| Skill nodes | **74** across 3 tiers: basics 30–18k (20), intermediate 18–10k (25), sdk 9–1k (29) |
| Prerequisite rows | **35** — progression is row-by-row, not a dependency graph |
| Structure | 1–5 levels per node × 2–6 quizzes per level × 5 puzzles per quiz |
| Attempt slots to complete the tree | **4,790** |
| Concept tags | `{opening, middle-game, endgame}` × `{fighting, tesuji, life-and-death, analysis, knowledge}` |

That 3×5 tag grid is already the vocabulary a difficulty model, or a mistake classifier, would
target. It does not need inventing.

### 2. The estimator works, and it is correctly implemented

`src/glicko2.py` is Glicko-2 as Glickman specifies it, plus the production details Lichess added:
first attempts only, damped updates for hinted contexts, a 700-point single-game delta cap, and
RD/volatility clamps.

It reproduces **Glickman's own worked example** to two decimal places (1464.05 / 151.52 / 0.06000
against the paper's 1464.06 / 151.52 / 0.05999). That is the test.

### 3. The finding that matters: gating breaks the scale

A skill tree does not serve random puzzles. Progression is gated, so players only meet puzzles
near their own level and the attempt matrix is *banded* rather than dense.

Recovering planted difficulties, 300 puzzles / 3,000 players:

| attempts per puzzle | random pairing | skill-tree gating |
|---|---|---|
| 10 | RMSE 258, ρ 0.88 | RMSE 428, ρ 0.47 |
| 40 | RMSE 167, ρ 0.97 | RMSE 373, ρ 0.77 |
| 160 | RMSE 113, ρ 0.97 | RMSE 304, ρ 0.81 |

Random pairing converges. **Gated pairing plateaus around 300 RMSE and stays there.**

The rank correlation is what diagnoses it. Under gating ρ climbs to 0.81 while RMSE stays around
340: the estimator learns *which puzzle is harder* but not *by how much*. That is scale drift
from weak linkage, not statistical noise, which is why adding data does not fix it. It is the
classic test-equating problem.

### 4. The remedy, and its honest price

The psychometric fix is **linking items**: common items spanning the whole range, served to
everyone, that pin the scale together. Dose-response at 40 attempts per puzzle:

| ungated fraction | RMSE | ρ |
|---|---|---|
| 0% | 338 | 0.81 |
| 25% | 284 | 0.88 |
| 50% | 234 | 0.92 |
| 100% | 165 | 0.97 |

Monotone, with no threshold to exploit: roughly 50 RMSE points per 25% of ungated traffic. **You
cannot buy your way out cheaply with a 10% sprinkle.**

The useful part is that Go Magic already owns an ungated instrument. **Go Diagnostics**
(`/go-tests/`, in beta) is not gated by the tree, and already promises *"an estimated puzzle rank
with a confidence range"* — that confidence range is Glicko RD. It is the natural linking test,
and this is an argument for serving more traffic through it.

---

## Limitations

- **Online vs batch.** This runs Glicko-2 sequentially, as a live system would. For a one-off
  backfill over an existing log you would fit jointly (batch MLE / IRT), which handles sparse
  linkage better. The gating penalty measured here is therefore an **upper bound** on the real
  cost, not an estimate of it. Quantifying that gap is the obvious next step and is not done here.
- **The outcome model is logistic on a single latent trait.** Real Go skill is not
  one-dimensional, which is the whole premise of a per-skill profile.
- **No hint damping in the sweep.** The Lichess weight is implemented in `play()` but the sweep
  runs undamped, so the tree regime is modelled slightly optimistically.
- Difficulties and skills are drawn from the same Gaussian. A real catalogue is lumpier.

---

## Run it

```sh
./src/parse_tree.py --json out/tree.json      # parse the live public skill tree
./src/recovery.py --quick                     # fast sweep
./src/recovery.py --puzzles 300 --reps 2      # the numbers above; writes out/recovery.png
```

`uv` handles dependencies through inline script metadata, so there is no environment to set up.

## Layout

```
src/parse_tree.py   public skill-tree parser
src/glicko2.py      Glicko-2 + Lichess production rules; validated against the paper
src/recovery.py     the recovery experiment and the plot
data/               a dated snapshot of the public page, so results reproduce offline
```
