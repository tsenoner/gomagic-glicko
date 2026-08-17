# gomagic-glicko

**How much data does it take to measure a Go puzzle's difficulty, instead of guessing it?**

Go Magic assigns puzzle difficulty by hand: a static 11-level table, one person's judgement per
puzzle, across **10,160 puzzles**, never revised by the millions of attempts already in their
database. This repo asks what it would take to replace that judgement with a measurement.

The short answer: skill-tree gating looks like it makes the problem intractable, and it does not.
Most of that penalty turns out to be an artefact of estimating online rather than a limit of the
data — which is a cheap fix, and the opposite of the conclusion the first pass reached.

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

### 3. Gating hurts, and at first it looked structural

A skill tree does not serve random puzzles. Progression is gated, so players only meet puzzles
near their own level and the attempt matrix is *banded* rather than dense.

Running Glicko-2 online, as a live system would, gated pairing looked like a wall: recovery
error plateaued around 300 RMSE and adding data barely moved it, while rank correlation climbed
to 0.81. The estimator was learning *which* puzzle was harder but not *by how much*, which reads
exactly like scale drift from weak linkage.

The obvious conclusion was that a skill tree structurally prevents its own labels from being
measurable. **That conclusion was wrong**, and the next section is how.

### 4. It was mostly the estimator, not the data

`src/batch_fit.py` refits the identical attempt logs as a joint Rasch MAP fit and scores both
estimators the same way (RMSE after affine alignment, since neither fixes an origin).
300 puzzles, 3,000 players:

| attempts/puzzle | regime | online Glicko | joint fit | online ρ | joint ρ |
|---|---|---|---|---|---|
| 10 | random | 220 | 205 | 0.90 | 0.92 |
| 10 | banded | 422 | 405 | 0.45 | 0.53 |
| 40 | random | 118 | 105 | 0.97 | 0.98 |
| 40 | banded | 284 | **200** | 0.78 | 0.91 |
| 160 | random | 78 | 54 | 0.99 | 1.00 |
| 160 | banded | **152** | **51** | 0.95 | 0.99 |

Read the last row. Under gating at 160 attempts per puzzle, online Glicko sits at 152 RMSE while
the joint fit reaches **51 — statistically indistinguishable from the 54 it achieves on randomly
paired data.** The gating penalty nearly disappears.

So the honest split:

- **At low volume the penalty is real and estimator-independent.** At 10 attempts per puzzle,
  banded costs you roughly 2× regardless of method (405 vs 205). That is an information limit in
  the data, and no cleverness recovers it.
- **At useful volume the penalty is mostly an artefact of estimating online.** Sequential updates
  are made against opponents whose own ratings are still noise, and under weak linkage that error
  never washes out. A joint fit sees the whole graph at once and does not care.

**The recommendation this produces is concrete and cheap: for a one-off backfill over an existing
log, fit jointly. Do not run online Glicko over history and conclude the data is inadequate.**
Reserve the online estimator for the live path, where it is the right tool.

Linking items still help — at 40 attempts per puzzle, ungated traffic buys roughly 50 RMSE points
per 25% added, monotonically — but they are a second-order fix next to choosing the right
estimator. Go Magic already owns the ungated instrument if they want it: **Go Diagnostics**
(`/go-tests/`, in beta) is not gated by the tree, and already promises *"an estimated puzzle rank
with a confidence range"*, which is Glicko RD by another name.

### 5. What their lives mechanic means for this

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

- **The joint fit is MAP, not MLE.** A Gaussian prior is required, not optional: at 10 attempts
  per puzzle most simulated players have one or two attempts and are perfectly separated, so the
  unregularised likelihood diverges. Shrinkage compresses the scale, which is why scoring allows
  an affine map — applied identically to both estimators.
- **The batch fit is given the true generating model.** No misspecification, so its numbers are
  a best case. Real data is not Rasch.
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
./src/recovery.py --puzzles 300 --reps 2      # the online sweep; writes out/recovery.png
./src/batch_fit.py --puzzles 300 --reps 2     # online vs joint fit, the section-4 table
```

`uv` handles dependencies through inline script metadata, so there is no environment to set up.

## Layout

```
src/parse_tree.py   public skill-tree parser
src/glicko2.py      Glicko-2 + Lichess production rules; validated against the paper
src/recovery.py     the recovery experiment and the plot
src/batch_fit.py    joint Rasch MAP refit, to test whether the finding was an artefact
data/               a dated snapshot of the public page, so results reproduce offline
```
