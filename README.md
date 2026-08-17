# gomagic-glicko

**How much data does it take to measure a Go puzzle's difficulty, instead of guessing it?**

Go Magic assigns puzzle difficulty by hand: a static 11-level table, one person's judgement per
puzzle, across **10,160 puzzles**, never revised by the millions of attempts already in their
database. This repo asks what it would take to replace that judgement with a measurement.

The short answer: skill-tree gating hurts, but far less than the first pass concluded. At useful
volume most of the penalty comes from *estimating online*, not from the shape of the data — a
one-off joint refit of the same log cuts recovery error by 63%. What survives is a smaller,
real penalty at low volume, which no choice of estimator fixes.

Nothing here uses private data. The skill-tree structure is parsed from a public page; everything
else is simulated.

**New to this?** [`docs/METHOD.md`](docs/METHOD.md) is the full write-up — what Elo, Glicko and
Glicko-2 each add and why it matters for puzzles, the algorithm step by step, how the experiment
works, and what the results mean. It assumes only that you have heard of Elo.

---

## What this does not claim

**It does not claim their difficulty labels are wrong.** Nobody outside the company can know
that; it needs their attempt log. This answers the question that comes *before* that one: if you
ran the estimator, how much data would you need before the answer meant anything?

That is a property of the estimator and the shape of the data, and it can be settled by
simulation.

---

## How error is measured

Neither estimator fixes an origin, so raw RMSE against the planted difficulties is meaningless
and some alignment is required. There are two ways to do it, they answer different questions, and
conflating them is the easiest way to fool yourself here — so every table below reports both:

|                     | what it removes                 | what it can still see                                                     |
| ------------------- | ------------------------------- | ------------------------------------------------------------------------- |
| **RMSE(off)** | a mean offset                   | ordering**and** spacing — a compressed scale still counts as error |
| **RMSE(aff)** | a full least-squares affine map | ordering only                                                             |

RMSE(aff) is scale-free *by construction*: algebraically it equals `sd(truth) · √(1 − r²)`, so it
is Pearson correlation wearing rating-point units. It cannot see scale error at all, and its
slope is fitted against the planted truth, which nobody has in production. So **RMSE(off) is the
primary number everywhere below**, and the fitted `slope` is printed beside it — 1.0 means the
fitted scale is already right, 2.6 means the fitted spread is 2.6× too narrow.

---

## Findings

### 1. Their Skill Tree, from the public page

`src/parse_tree.py` reads the `data-*` attributes on `gomagic.org/go-problems/`:

|                                    |                                                                                                    |
| ---------------------------------- | -------------------------------------------------------------------------------------------------- |
| Skill nodes                        | **74** across 3 tiers: basics 30–18k (20), intermediate 18–10k (25), sdk 9–1k (29)        |
| Prerequisite rows                  | **35** — progression is row-by-row, not a dependency graph                                  |
| Structure                          | 1–5 levels per node × 2–6 quizzes per level × 5 puzzles per quiz                               |
| Attempt slots to complete the tree | **4,790**                                                                                    |
| Concept tags                       | `{opening, middle-game, endgame}` × `{fighting, tesuji, life-and-death, analysis, knowledge}` |

That 3×5 tag grid is already the vocabulary a difficulty model, or a mistake classifier, would
target. It does not need inventing.

### 2. The estimator works, and it is correctly implemented

`src/glicko2.py` is Glicko-2 as Glickman specifies it, plus the production details Lichess added:
first attempts only, damped updates for hinted contexts, a 700-point single-game delta cap, and
RD/volatility clamps.

`./tests/test_glicko2.py` runs **Glickman's own worked example** from the paper and gets
1464.0507 / 151.5165 / 0.059996 against the paper's printed 1464.06 / 151.52 / 0.05999. The paper
rounds its intermediate steps, so the residual hundredth is its rounding, not a disagreement — an
actual error in any of steps 3–8 moves those numbers by whole points. The same file also pins the
clamps, the empty-rating-period path, the saturated-expectation path, and the damping weight.

### 3. Gating hurts, and it distorts the scale more than the ordering

A skill tree does not serve random puzzles. Progression is gated, so players only meet puzzles
near their own level and the attempt matrix is *banded* rather than dense.

Online Glicko-2, as a live system would run it. 300 puzzles, 3,000 players, 2 reps:

| attempts/puzzle | random RMSE(off) | random ρ | gated RMSE(off) | gated ρ | gated slope |
| --------------- | ---------------- | --------- | --------------- | -------- | ----------- |
| 10              | 247              | 0.88      | 404             | 0.41     | 1.17        |
| 40              | 164              | 0.97      | 349             | 0.78     | 2.63        |
| 160             | 104              | 0.99      | 279             | 0.95     | 2.35        |

Gated recovery error does **not** plateau — it falls steadily, by roughly 28 points per doubling
of attempts across the full 3→160 sweep, against 39 points per doubling for random pairing. It is
slower convergence, not a wall. But because it converges more slowly, the *gap* widens with
volume rather than closing: gated is 1.6× worse at 10 attempts per puzzle, 2.1× at 40, and 2.7× at
160. Buying more traffic does not buy your way out of gating.

The interesting part is *how* it is worse. At 160 attempts per puzzle the gated estimator has
essentially learned the ordering — **ρ 0.95** — while still sitting at 279 RMSE with a **slope of
2.35**. It knows which puzzle is harder and understates by how much, by a factor of two. That is
scale compression from weak linkage, not noise, and it is the specific thing to fix.

### 4. Most of that is the online estimator, not the data

`src/batch_fit.py` refits **the identical attempt log** — one list, handed to both estimators — as
a joint Rasch MAP fit. Both files seed the world and the log the same way, so the `online` rows
below are the *same runs* as the section-3 table, digit for digit, and the two sections are
directly comparable. 300 puzzles, 3,000 players, 2 reps:

| attempts | regime | estimator | RMSE(off)     | RMSE(aff) | slope | ρ   |
| -------- | ------ | --------- | ------------- | --------- | ----- | ---- |
| 10       | random | online    | 247           | 212       | 1.48  | 0.88 |
| 10       | random | batch     | 237           | 212       | 1.37  | 0.88 |
| 10       | gated  | online    | 404           | 402       | 1.17  | 0.41 |
| 10       | gated  | batch     | **383** | 380       | 1.27  | 0.50 |
| 40       | random | online    | 164           | 116       | 1.37  | 0.97 |
| 40       | random | batch     | 129           | 105       | 1.21  | 0.97 |
| 40       | gated  | online    | 349           | 271       | 2.63  | 0.78 |
| 40       | gated  | batch     | **241** | 139       | 1.87  | 0.95 |
| 160      | random | online    | 104           | 76        | 1.20  | 0.99 |
| 160      | random | batch     | 63            | 51        | 1.09  | 0.99 |
| 160      | gated  | online    | 279           | 139       | 2.35  | 0.95 |
| 160      | gated  | batch     | **103** | 39        | 1.28  | 1.00 |

Read the last two rows. Under gating at 160 attempts per puzzle, online Glicko sits at 279 RMSE
with its scale compressed 2.35×; the joint fit on the same log reaches **103 with slope 1.28** — a
63% cut in error, and most of the scale compression gone too. So the honest split:

- **At low volume the penalty is real and estimator-independent.** At 10 attempts per puzzle the
  joint fit buys almost nothing (404 → 383) and gated is still ~1.6× worse than random. That is an
  information limit in the data, and no cleverness recovers it.
- **At useful volume the penalty is mostly an artefact of estimating online.** Sequential updates
  are made against opponents whose own ratings are still noise, and under weak linkage that error
  never washes out. A joint fit sees the whole graph at once and does not care.
- **It does not vanish, though.** At 160 attempts the joint fit is still 103 gated vs 63 random —
  a residual 1.6× that is a property of the data. Earlier drafts of this README claimed the gap
  "nearly disappears"; that was an artefact of reading it off the scale-free metric, where gated
  (39) even beats random (51) because the affine map hands back the compressed scale for free.

**The recommendation this produces is concrete and cheap: for a one-off backfill over an existing
log, fit jointly. Do not run online Glicko over history and conclude the data is inadequate.**
Reserve the online estimator for the live path, where it is the right tool.

### 5. Linking items still help, and the dose-response is buyable

Common items served ungated to everyone are the standard psychometric fix for a poorly connected
design. At 40 attempts per puzzle (`--linking 0.25 0.5 1.0`):

| ungated fraction | RMSE(off) | slope | ρ   |
| ---------------- | --------- | ----- | ---- |
| 0%               | 349       | 2.63  | 0.78 |
| 25%              | 281       | 1.75  | 0.88 |
| 50%              | 234       | 1.57  | 0.92 |
| 100%             | 164       | 1.37  | 0.97 |

Monotone, with no threshold to exploit, and with diminishing returns: the first 25% of ungated
traffic buys 68 RMSE points, the next 47, and the top half about 35 per 25%. Most of the scale
compression goes with it (slope 2.63 → 1.37). The 100% row reproduces the random-pairing row
exactly (164 / 1.37 / 0.97), which is the consistency check that the gating knob does what it says.

Next to choosing the right estimator this is second-order — the joint refit is free and buys more
— but it is the fix that also helps the *live* path, which cannot be batch-fitted. Go Magic
already owns the ungated instrument: **Go Diagnostics** (`/go-tests/`, in beta) is not gated by
the tree, and already promises *"an estimated puzzle rank with a confidence range"*, which is
Glicko RD by another name.

### 6. What their lives mechanic means for this

Go Magic gives **one or two lives per puzzle**, deliberately, to push players to read the position
out before touching it. You may retry after failing, but you earn no coins or XP.

Three consequences:

- **First-attempt resolution almost certainly exists in their data.** A lives counter has to be
  tracked per user per puzzle to work at all, which is the exact field this needs. The blocking
  dependency is therefore much smaller than it looked.
- **Post-failure retries must be excluded**, and now there is a principled reason rather than a
  borrowed convention: those attempts are unrewarded *and* taken after seeing the answer, so they
  measure recall, not difficulty. Lichess's first-attempt-only rule falls straight out.
- **Two lives is a modelling decision, not a detail.** "Solved on the first life" and "solved
  within two lives" are different binary outcomes and produce different difficulty scales. Pick
  one deliberately. First-life-only is cleaner and matches the estimator's assumptions; solved
  within-lives is closer to what the player experiences as success.

One nice side effect: read-it-out-first discourages careless clicking, so the outcomes carry less
guessing noise than a typical puzzle app. That helps difficulty estimation.

## Limitations

- **The joint fit is MAP, and the prior sets the scale.** A Gaussian prior is required, not
  optional: at 10 attempts per puzzle most simulated players have one or two attempts and are
  perfectly separated, so the unregularised likelihood diverges. But prior strength trades against
  scale compression, and compression is invisible to a scale-free metric. So `--l2` defaults to
  `(SCALE/TRUE_SD)² = 0.1386`, the value implied by the population the simulation actually draws
  from, rather than a tuned number — tuning it against the planted truth would be picking a knob
  by peeking at the answer. That default is the *pessimistic* end for the batch fit: at 160
  attempts per puzzle, gated, weakening it to 0.05 and then 0.03 takes the joint fit from 101 → 41
  → 33 RMSE(off), with slope going 1.27 → 1.06 → 1.00. The reported batch advantage is therefore a
  lower bound, and section 4's conclusion would only get stronger with a tuned prior. What does
  *not* improve is the 10-attempt cell (385 → 366 → 364), so the low-volume information limit is
  not a prior artefact either. `--l2` is there to check all of this yourself.
- **RMSE(aff) is an oracle metric.** Its slope and intercept are least-squares-fitted against the
  planted difficulties, which a real deployment does not have. Realising a rescale in production
  needs anchor items of known difficulty. It is reported only as the scale-free companion to
  RMSE(off), never on its own.
- **The batch fit is given the true generating model.** No misspecification, so its numbers are
  a best case. Real data is not Rasch.
- **The outcome model is logistic on a single latent trait.** Real Go skill is not
  one-dimensional, which is the whole premise of a per-skill profile.
- **Two reps, and no confidence intervals anywhere.** Every table is a mean over `--reps` worlds
  and nothing computes a standard error, so gaps of a few RMSE points between adjacent cells are
  not resolvable. The gaps the conclusions rest on are 100+ points; the small ones are not claimed.
- **No hint damping in the sweep.** The Lichess weight is implemented and tested in `play()` but
  the sweep runs undamped, so the tree regime is modelled slightly optimistically.
- Difficulties and skills are drawn from the same Gaussian. A real catalogue is lumpier.

### Sourcing

The committed snapshot `data/skilltree-2026-08-16.html` backs the section-1 inventory, the
**10,160 puzzles** figure, and the 5-puzzles-per-quiz multiplier (*"a quiz — a short series of 5
puzzles"*). It does **not** contain the word "difficulty", so the 11-level table, the lives
mechanic in section 6, and the Go Diagnostics quote in section 5 come from other pages of
gomagic.org that are not snapshotted here and cannot be checked offline.

The Lichess constants in `glicko2.py` (`MIN_DEVIATION` 45, `MAX_DEVIATION` 500, `MAX_VOLATILITY`
0.1, `MAX_RATING_DELTA` 700, `TAU` 0.75) **have been checked against the source** and all six are
real — five in lila's `modules/rating/src/main/Glicko.scala`, and `TAU` in the separate `scalachess`
library, which is where Lichess's Glicko-2 arithmetic actually lives. lila's
`PuzzleFinisher.scala` also confirms the premise verbatim: *"we treat the solve as a game where the
player is white and the puzzle is black"*.

Three divergences are worth knowing, and [`docs/METHOD.md`](docs/METHOD.md) section 4 has the
line-by-line citations: `DEFAULT_RD` 350 is Glickman's, where lila starts competitors at 500; lila
clamps ratings to `[400, 4000]`, which this repo does not, and that clamp is what makes lila immune
to the saturation branch; and lila's hint damping is asymmetric and theme-based (a hinted win is
weighted 0.2, a hinted loss 0.7) where `play()` takes one symmetric `weight`.

---

## Run it

```sh
./tests/test_glicko2.py                                  # validate the estimator (the section-2 claim)
./src/parse_tree.py --html data/skilltree-2026-08-16.html # section 1, offline from the snapshot
./src/parse_tree.py --json out/tree.json                 # or fetch the live public page
./src/recovery.py --quick                                # fast sweep, for iterating
./src/recovery.py --puzzles 300 --reps 2                 # the section-3 table; writes out/recovery.png
./src/batch_fit.py --puzzles 300 --reps 2                # the section-4 table
./src/recovery.py --puzzles 300 --reps 2 --linking 0.25 0.5 1.0   # the section-5 table
```

Every table above is one of these commands at its printed defaults, seed included. `uv` handles
dependencies through inline script metadata, so there is no environment to set up.

## Layout

```
docs/METHOD.md          the full method write-up: what, why and how, from Elo onwards
src/parse_tree.py       public skill-tree parser
src/glicko2.py          Glicko-2 + Lichess production rules
src/recovery.py         the planted world, the attempt log, online fitting, scoring, the plot
src/batch_fit.py        joint Rasch MAP refit of the same log, to test the online artefact
tests/test_glicko2.py   Glickman's worked example and the clamps
data/                   a dated snapshot of the public page, so section 1 reproduces offline
```

`recovery.py` owns the shared pieces — `make_log` builds the attempt log, `replay` fits it online,
`score_values` computes both error metrics — so `batch_fit.py` scores a different estimator on the
same log rather than re-deriving its own.
