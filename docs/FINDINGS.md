# Findings: what the simulation shows

Every result behind [`../README.md`](../README.md), with the tables, the confidence intervals, and
the caveats that qualify them. [`METHOD.md`](METHOD.md) is the long-form companion — what Elo,
Glicko and Glicko-2 each add, the algorithm step by step, and how the experiment is built.
This file is the summary a reviewer can read in one pass.

Every figure below is a mean over **10 planted worlds**, every primary error figure carries a
**95% confidence interval** (the secondary columns — slope, ρ, ±100 — are plain means), and every
regime-vs-regime claim is a *paired* contrast on the same worlds — with one marked exception, the
exploratory 640–1,280-attempt check in section 3, which is a 2–3-rep directional probe and says
so. Nothing here rests on a difference the reruns cannot resolve.

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

## The scale, and what the simulated world contains

Every number below is in rating points, so the conversion to ranks and the range of the planted
world both have to be stated before any of them mean anything. `describe_scale()` prints this
block at the top of every run, and the figure caption repeats it:

|                          |                                                                                                    |
| ------------------------ | -------------------------------------------------------------------------------------------------- |
| rank ↔ rating            | **1 rank = 100 rating points, 1d = 2100** (so 1k = 2000, 20k = 100), the EGF nominal convention |
| planted truth            | **N(1500, 467)** — the *same* distribution for puzzle difficulty and for player skill        |
| 95% of the planted mass  | 567 … 2433 = **15k … 4d**                                                                    |
| 99.7% (±3 sd)            | 100 … 2900 = **20k … 9d**, centred on 1500 = **6k**                                     |
| the no-information ceiling | **RMSE 467.** An estimator that guesses 1500 for every puzzle scores exactly the population sd |

That last row is the one to keep in mind: an RMSE of 440 is not "somewhat bad", it is **nothing
learned**. And the ±100 target on the plot is one rank — one *nominal* rank, which the next
subsection shows is an honest rank at 1d and an optimistic one lower down.

**Two honest mismatches with the real catalogue**, both flagged in `src/recovery.py`:

- Go Magic's tree spans **30k–1d**, but the planted population runs to 9d and stops at 20k. About
  **10% of planted puzzles come out above 1d** — harder than any puzzle Go Magic actually has —
  and nothing is planted in the 30k–20k range where the tree's first tier lives.
- The 100-points-per-rank map is **linear, and real Go ranks are not.** This is the EGF *label*
  convention, which is linear by decree — and as a label it is accurate: fitted against 4,983
  active EGF players the slope is 101.4 points per rank at 20k–11k, 97.2 at 10k–1k, 99.5 at 1d–7d.
  The *win-probability* meaning is what fails. Measured over 675,451 European tournament games
  ([`RESEARCH.md`](RESEARCH.md) §1, reproducible with `./src/egd_scale.py`), one rank is worth:

  | | 13k | 10k | 5k | 1k | **1d** | 4d | 6d |
  |---|---|---|---|---|---|---|---|
  | stronger player wins | 55.3% | 56.3% | 56.7% | 60.0% | **63.5%** | 67.5% | 77.4% |
  | Elo-400 points per rank | 37 | 44 | 47 | 71 | **96** | 127 | 214 |

  **So "±100 points ≈ one rank" is measured to be almost exactly right at 1d — and about 2.5×
  too generous at 10k**, which is where the tree's first tiers sit. A rank is roughly 5× wider in
  rating points at 6d than in the middle of the kyu range, because Go's ranks are a *handicap*
  ladder: one rank means "one stone makes it fair", a fixed amount of compensation rather than a
  fixed probability. Error figures quoted in ranks below should be read as a **dan-calibrated lower
  bound**: a 300-point error is three ranks at 1d but nearer seven at 10k.

Neither affects the *estimator* — it never sees a rank — but both mean the simulated population is
a stylised Go population rather than Go Magic's. [`RESEARCH.md`](RESEARCH.md) §1 has the
measurement, the four competing published mappings scored against it, and what remains genuinely
unsettled (chiefly: everything below 12 kyu, where no trustworthy public measurement exists).

---

## 1. Their Skill Tree, from the public page

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

## 1b. This is not a new idea, and the honest version is better

Deriving Go puzzle difficulty from attempt data has been production practice since roughly 1999.
**goproblems.com** rates problems by Elo with a per-problem K that decays from ~127 to ~10 as
attempts accumulate; **Tsumego Hero** uses EGF GoR and updates both sides on every attempt;
**101weiqi** puts problem difficulty on the same axis as player rating. Lichess does the exact
thing this repo simulates — a solve attempt treated as a Glicko-2 game between player and puzzle —
across ~6.1M puzzles, published CC0.

What is left that is genuinely open: **Glicko-2 rather than Elo/GoR** (neither Go implementation
carries an explicit rating deviation, and goproblems' decaying K is an RD approximated badly);
**anchoring**, which is unsolved in the wild and which both mature systems patch with clamps;
**doing it under a gated tree** with a lives mechanic censoring the log; and **per-cell estimation
on a 3x5 concept grid**, which nobody does.

And the strongest evidence anyone wants it: OGS has had an open issue for *Glicko rating for
puzzles* since February 2022 — motivated by puzzles having "static, often outdated ratings" —
while already recording the attempt counts it would need.

[`PROBLEM-SOURCES.md`](PROBLEM-SOURCES.md) has the survey, the licence audit, and the
taxonomy mapping.

## 2. The estimator works, and it is correctly implemented

`src/glicko2.py` is Glicko-2 as Glickman specifies it, plus the production details Lichess added:
first attempts only, damped updates for hinted contexts, a 700-point single-game delta cap, and
RD/volatility clamps.

`./tests/test_glicko2.py` runs **Glickman's own worked example** from the paper and gets
1464.0507 / 151.5165 / 0.059996 against the paper's printed 1464.06 / 151.52 / 0.05999. The paper
rounds its intermediate steps, so the residual hundredth is its rounding, not a disagreement — an
actual error in any of steps 3–8 moves those numbers by whole points. The same file also pins the
clamps, the empty-rating-period path, the saturated-expectation path, and the damping weight.

## 3. Gating hurts, and it distorts the scale more than the ordering

A skill tree does not serve random puzzles. Progression is gated, so players only meet puzzles
near their own level and the attempt matrix is *banded* rather than dense.

Online Glicko-2, as a live system would run it. 300 puzzles, 3,000 players, 10 reps:

| attempts/puzzle | random RMSE(off)      | random ρ | gated RMSE(off)       | gated ρ | gated slope | paired gap        |
| --------------- | --------------------- | --------- | --------------------- | -------- | ----------- | ----------------- |
| 10              | 249.5 ± 4.8 | 0.89      | 408.2 ± 5.1 | 0.44     | 1.26        | **+158.6 ± 4.3** |
| 40              | 166.8 ± 4.1 | 0.97      | 355.2 ± 6.1 | 0.78     | 2.64        | **+188.4 ± 5.1** |
| 160             | 106.5 ± 3.4 | 0.99      | 287.1 ± 7.4 | 0.94     | 2.36        | **+180.6 ± 8.9** |

The last column is the paired contrast — the same planted worlds, with identically seeded log
streams, in both regimes — which is the *correct* interval for a gap, so read it rather than eyeballing the
overlap of the two per-regime intervals. It is not automatically the tighter one: pairing buys
1.4–1.6× at 10 and 40 attempts, and at 160 it is slightly **wider** than an independent-samples
combination (±8.9 against ≈±8.1), because by then the two regimes respond differently enough to
the same planted world that differencing stops cancelling. Every gap in this repo is significant
at 95% either way.

Gated recovery error does **not** plateau — it falls steadily, by roughly 28 points per doubling
of attempts across the full 3→160 sweep, against 39 points per doubling for random pairing. It is
slower convergence, not a wall. But because it converges more slowly, the *ratio* widens with
volume: gated is 1.6× worse at 10 attempts per puzzle, 2.1× at 40, and 2.7× at 160. Buying more
traffic does not buy your way out of gating.

The interesting part is *how* it is worse. At 160 attempts per puzzle the gated estimator has
essentially learned the ordering — **ρ 0.94** — while still sitting at 287 RMSE with a **slope of
2.36**. It knows which puzzle is harder and understates by how much, by a factor of two. That is
scale compression from weak linkage, not noise, and it is the specific thing to fix.

**A trap for anyone extending the sweep.** The obvious next question is what happens past 160, and
running it naively suggests the penalty evaporates — gated reaches 93.5 RMSE at 1,280 attempts
against random's 64.9, a mere 1.4×. That is an artefact. `make_log` falls back to "the nearest N
players" when the ±300 band cannot supply N, and past 160 attempts that fallback fires constantly
— hardest of all on the tail puzzles, handing them precisely the wide-range comparisons gating is
supposed to deny. Scale the population so the band stays a band and the effect disappears:

| attempts | players | fallback rate | random | gated | ratio          |
| -------- | ------- | ------------- | ------ | ----- | -------------- |
| 640      | 3,000   | 16%           | 73.8   | 176.5 | 2.39×         |
| 640      | 30,000  | **0%**  | 102.9  | 286.1 | **2.78×** |
| 1,280    | 3,000   | 58%           | 64.9   | 93.5  | 1.44×         |
| 1,280    | 30,000  | **2%**  | 91.4   | 253.9 | **2.78×** |

The apparent convergence tracks the fallback rate exactly. With gating intact the penalty is
**flat at ~2.8× out to 1,280 attempts per puzzle**, which strengthens rather than weakens the
conclusion above. (Compare within rows only: more players means fewer attempts each, so absolute
values shift. And these four rows are the one exception to the 10-worlds-with-intervals rule
stated at the top: they are a 2–3-rep directional check, deliberately not promoted into the
headline tables.) `--sweep` exists so this is checkable, and its `--help` carries the warning.

## 4. Most of that is the online estimator, not the data

`src/batch_fit.py` refits **the identical attempt log** — one list, handed to both estimators — as
a joint Rasch MAP fit. Both files seed the world and the log the same way, so the `online` rows
below are the *same runs* as the section-3 table, digit for digit, and the two sections are
directly comparable. 300 puzzles, 3,000 players, 10 reps:

| attempts | regime | estimator | RMSE(off)             | RMSE(aff) | slope | ρ   | paired batch − online |
| -------- | ------ | --------- | --------------------- | --------- | ----- | ---- | --------------------- |
| 10       | random | online    | 249.5 ± 4.8 | 215       | 1.46  | 0.89 |                       |
| 10       | random | batch     | 237.8 ± 5.1 | 211       | 1.37  | 0.89 | −11.8 ± 1.6  |
| 10       | gated  | online    | 408.2 ± 5.1 | 406       | 1.26  | 0.44 |                       |
| 10       | gated  | batch     | **388.1 ± 5.3** | 383 | 1.34  | 0.53 | −20.1 ± 3.2  |
| 40       | random | online    | 166.8 ± 4.1 | 118       | 1.37  | 0.97 |                       |
| 40       | random | batch     | 133.9 ± 4.4 | 108       | 1.22  | 0.98 | −32.9 ± 2.7  |
| 40       | gated  | online    | 355.2 ± 6.1 | 277       | 2.64  | 0.78 |                       |
| 40       | gated  | batch     | **251.5 ± 7.8** | 145 | 1.92  | 0.95 | −103.7 ± 2.6 |
| 160      | random | online    | 106.5 ± 3.4 | 77        | 1.20  | 0.99 |                       |
| 160      | random | batch     | 63.7 ± 3.1  | 52        | 1.09  | 0.99 | −42.8 ± 1.4  |
| 160      | gated  | online    | 287.1 ± 7.4 | 147       | 2.36  | 0.94 |                       |
| 160      | gated  | batch     | **111.5 ± 4.0** | 40  | 1.30  | 1.00 | −175.6 ± 6.3 |

The dashed curves in `out/recovery.png` are this table's `batch` rows across the whole sweep:
`recovery.py` calls the same `fit` on the same log, so the figure and this table cannot drift.

The last column is the tightest interval in the repo, and here the pairing genuinely earns it: the
two estimators run on *one shared log per rep*, so the contrast is paired twice over — same world,
same log — and only the estimator differs. That buys 1.3–4.4× over an independent-samples
combination, against 1.4–1.6× for the regime contrasts in section 3.

Read the last two rows. Under gating at 160 attempts per puzzle, online Glicko sits at 287 RMSE
with its scale compressed 2.36×; the joint fit on the same log reaches **111.5 with slope 1.30** —
a 61% cut in error, and most of the scale compression gone too. So the honest split:

- **At low volume the penalty is real and estimator-independent.** At 10 attempts per puzzle the
  joint fit buys almost nothing (408 → 388, a 4.9% cut) and gated is still ~1.6× worse than random.
  That is an information limit in the data, and no cleverness recovers it.
- **At useful volume the penalty is mostly an artefact of estimating online.** Sequential updates
  are made against opponents whose own ratings are still noise, and under weak linkage that error
  never washes out. A joint fit sees the whole graph at once and does not care.
- **It does not vanish, though.** At 160 attempts the joint fit is still 111.5 gated vs 63.7 random
  — a residual 1.75× that is a property of the data. Earlier drafts of this README claimed the gap
  "nearly disappears"; that was an artefact of reading it off the scale-free metric, where gated
  (40) even beats random (52) because the affine map hands back the compressed scale for free.

**The recommendation this produces is concrete and cheap: for a one-off backfill over an existing
log, fit jointly. Do not run online Glicko over history and conclude the data is inadequate.**
Reserve the online estimator for the live path, where it is the right tool.

## 5. Linking items still help, and the dose-response is buyable

Common items served ungated to everyone are the standard psychometric fix for a poorly connected
design. At 40 attempts per puzzle (`--linking 0.25 0.5 1.0`):

| ungated fraction | RMSE(off)             | slope | ρ   | paired vs 0%       |
| ---------------- | --------------------- | ----- | ---- | ------------------ |
| 0%               | 355.2 ± 6.1 | 2.64  | 0.78 |                    |
| 25%              | 297.9 ± 10.9 | 1.85  | 0.87 | −57.2 ± 6.6  |
| 50%              | 248.6 ± 7.7 | 1.59  | 0.92 | −106.5 ± 5.6 |
| 100%             | 166.8 ± 4.1 | 1.37  | 0.97 | −188.4 ± 5.1 |

Monotone, with no threshold to exploit, and with diminishing returns: the first 25% of ungated
traffic buys 57 RMSE points, the next 49, and the top half about 41 per 25%. Most of the scale
compression goes with it (slope 2.64 → 1.37). The 100% row reproduces the random-pairing row
exactly (166.8 / 1.37 / 0.97), the consistency check that the gating knob does what it says.

At 10 reps even the **10% dose is significant at every volume** — −14.7 ± 7.0 at 10 attempts per
puzzle, −20.8 ± 5.2 at 40, −28.1 ± 5.7 at 160 — and the benefit grows with volume, because linking
items carry weak information per attempt that needs traffic to accumulate. An earlier 2-rep reading
put the low-volume effect inside the noise; it is not. Those three figures need `--linking 0.1`:
the default dose is now 25%, the one the chart draws and the one the recommendation quotes.

Next to choosing the right estimator this is second-order — the joint refit is free and buys more
— but it is the fix that also helps the *live* path, which cannot be batch-fitted. Go Magic
already owns the ungated instrument: **Go Diagnostics** (`/go-tests/`, in beta) is not gated by
the tree, and already promises *"an estimated puzzle rank with a confidence range"*, which is
Glicko RD by another name.

## 6. What their lives mechanic means for this

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

## 7. Uneven traffic costs as much as gating does, and it wrecks the ordering

Sections 3–5 give every puzzle the *same* number of attempts, which is the one thing a
prerequisite tree certainly does not do. Everybody meets the first node; only survivors reach the
last. `--funnel f` makes traffic decay with difficulty — `f` is the hardest puzzle's share of the
easiest one's attempts — and renormalises so the **mean** attempts per puzzle is unchanged. That
isolates the *shape* of the traffic from its volume: both columns below are the same 12,000
attempts, distributed differently.

At `--funnel 0.02` and 40 attempts per puzzle on average, the easiest puzzle gets 159 attempts, the
median 22, the hardest 3.

| attempts (mean) | regime | flat traffic          | funnelled (0.02)      | paired cost        | ρ flat → funnel |
| --------------- | ------ | --------------------- | --------------------- | ------------------ | ---------------- |
| 40              | random | 166.8 ± 4.1 | 216.3 ± 10.0 | **+49.5 ± 7.3** | 0.97 → 0.92     |
| 40              | gated  | 355.2 ± 6.1 | 386.4 ± 5.5 | **+31.3 ± 5.6** | 0.78 → **0.52** |
| 160             | random | 106.5 ± 3.4 | 146.9 ± 6.6 | **+40.4 ± 5.8** | 0.99 → 0.98     |
| 160             | gated  | 287.1 ± 7.4 | 326.2 ± 7.2 | **+39.2 ± 7.1** | 0.94 → **0.78** |

Three things follow, and the third is the one that changes a recommendation:

- **Uneven traffic is a first-class cost, not a detail.** 40–50 RMSE points at matched total
  volume, comparable to a 25% linking-item budget. Sections 3–5 are therefore optimistic about a
  real catalogue, in a direction that was previously unquantified.
- **It hurts ungated pairing too** (+40 to +50), so it is not a gating effect. It is the plain
  fact that a puzzle with 3 attempts cannot be measured no matter who attempted it, and RMSE is
  dominated by the starved tail.
- **It degrades the *ordering*, which gating alone did not.** Under gating at 160 attempts, ρ falls
  from 0.94 to 0.78. That matters because the ordering is what a mislabel-review queue rests on —
  the one application that survives a compressed scale. Under realistic traffic it is weaker than
  the flat-traffic tables imply, which is an argument for gating that queue on per-puzzle attempt
  counts rather than running it over the whole catalogue.

The operational consequence is the same per-puzzle readiness gate the rest of this repo argues
for, with more force: **the catalogue will never be uniformly measured, so plan for a
measured head and a hand-labelled tail rather than a cutover.**

**One honest asterisk on the gated funnel rows.** The funnel pushes the *head* puzzles' attempt
counts far past what the ±300 band can supply (the easiest puzzle wants 636 attempts at mean 160),
so `make_log`'s nearest-N fallback — the same artefact the section-3 trap describes — fires on 6%
of puzzles carrying **~21% of attempts** at mean 160 (1% of puzzles, ~4% of attempts, at mean 40),
and the run prints its partly-ungated warning. Those wide comparisons *help* the estimator, so the
gated funnel cells are optimistic: the true cost of funnelled traffic under intact gating is at
least what this table shows, and the conclusions above survive in the direction that matters.

## Limitations

- **The joint fit is MAP, and the prior sets the scale.** A Gaussian prior is required, not
  optional: at 10 attempts per puzzle most simulated players have one or two attempts and are
  perfectly separated, so the unregularised likelihood diverges. But prior strength trades against
  scale compression, and compression is invisible to a scale-free metric. So `--l2` defaults to
  `(SCALE/TRUE_SD)² = 0.1386`, the value implied by the population the simulation actually draws
  from, rather than a tuned number — tuning it against the planted truth would be picking a knob
  by peeking at the answer. That default is the *pessimistic* end for the batch fit: at 160
  attempts per puzzle, gated, weakening it to 0.05 and then 0.03 takes the joint fit from 110 → 47
  → 34 RMSE(off), with slope going 1.29 → 1.08 → 1.02. The reported batch advantage is therefore a
  lower bound, and section 4's conclusion would only get stronger with a tuned prior. What does
  *not* improve is the 10-attempt cell (388 → 365 → 358), so the low-volume information limit is
  not a prior artefact either. `--l2` is there to check all of this yourself.
- **RMSE(aff) is an oracle metric.** Its slope and intercept are least-squares-fitted against the
  planted difficulties, which a real deployment does not have. Realising a rescale in production
  needs anchor items of known difficulty. It is reported only as the scale-free companion to
  RMSE(off), never on its own.
- **The batch fit is given the true generating model.** No misspecification, so its numbers are
  a best case. Real data is not Rasch.
- **The outcome model is logistic on a single latent trait.** Real Go skill is not
  one-dimensional, which is the whole premise of a per-skill profile.
- **No hint damping in the sweep.** The Lichess weight is implemented and tested in `play()` but
  the sweep runs undamped, so the tree regime is modelled slightly optimistically.
- **The rank map is linear and the planted range is not the catalogue's.** See "The scale" above:
  ~10% of planted puzzles land above 1d, nothing lands below 20k, and 100 points per rank is least
  accurate at high kyu, where the tree's first tier sits.
- Difficulties and skills are drawn from the same Gaussian. A real catalogue is lumpier.
- **The funnel is a shape, not a fit.** Section 7's decay is exponential in the difficulty
  percentile because that is the simplest one-parameter family with the right qualitative
  behaviour. Real tree traffic follows the prerequisite graph and the drop-off between nodes;
  matching it needs their numbers, and the section reports a direction and a rough magnitude
  rather than a prediction.
- **Confidence intervals cover the simulation, not the modelling.** Every figure is a mean over 10
  planted worlds, the primary error figures carry a 95% t interval, and the regime contrasts are
  paired, so sampling noise is quantified. That says nothing about whether the *model* is right —
  the bullets above are the uncertainty that matters and none of them has an error bar.

## Sourcing

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

Three divergences are worth knowing, and [`METHOD.md`](METHOD.md) section 4 has the
line-by-line citations: `DEFAULT_RD` 350 is Glickman's, where lila starts competitors at 500; lila
clamps ratings to `[400, 4000]`, which this repo does not, and that clamp is what makes lila immune
to the saturation branch; and lila's hint damping is asymmetric and theme-based (a hinted win is
weighted 0.2, a hinted loss 0.7) where `play()` takes one symmetric `weight`.
