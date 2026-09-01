# Research: the design questions this repo does not settle by itself

The simulation answers one question — *how much data before a measured difficulty means
anything?* Reviewing it raised five that it cannot answer, because they are settled by literature
and production practice rather than by re-running the sweep:

1. **Cold start.** New players arrive unrated. Wait, exclude, or co-estimate?
2. **Per-skill ratings.** Strong at life-and-death, weak at endgame — one rating or fifteen?
3. **Time to solve.** A 10k may solve a 5k problem given fifteen minutes. Usable signal?
4. **Player ratings for real games.** Can head-to-head play share this pool, or does it need Elo?
5. **Blending disciplines.** Per-tag ratings shrunk toward an overall, as surface Elo does in tennis.

Plus one the repo got wrong on its own terms: **what is a Go rank actually worth in rating
points?**

## How this was produced, and how much to trust it

Six parallel literature sweeps, each followed by an adversarial fact-checker instructed to refute
any claim whose cited source did not support it, then a synthesis that dropped what was refuted,
then a completeness critic. Fourteen agents, ~700 retrievals.

**Read the two caveat sections at the end before acting on anything here.** The fact-checking
corrected several figures that circulate widely (a tenfold error in Pelánek's fitted constant, a
3× error in a CAT standard-error formula, a misattributed Duolingo quote), and the completeness
critic found real overclaims in the brief itself — including one recommendation that contradicts
this repo's own measurement. Those are listed rather than quietly fixed, because which claims are
load-bearing on a single weak source is itself part of the answer.

Nothing in this document has been implemented. It is the reading behind
[`OPEN-QUESTIONS.md`](OPEN-QUESTIONS.md), not a report of work done — **with one exception, flagged in place.**
Section 1 was originally a comparison of four published mappings that concluded the literature
could not be reconciled. It has since been replaced by a **primary measurement** against the
European Go Database's own published statistics, because measuring the disagreement turned out to
be cheaper than arbitrating it. That section carries its own provenance note, method, and caveats.

---

# Technical Brief: Rating-System Design Questions for Go Magic

*Synthesis of six researched-and-verified topic dossiers. Every claim below survived an adversarial fact-check against primary sources; claims that were refuted in verification have been dropped or corrected in place, and the corrections are noted where a reader might otherwise expect the popular version.*

---

## 0. Answers in one line each

| # | Question | Answer |
|---|---|---|
| 6 | Real kyu/dan → rating-points mapping? | **Measured, not inferred** (§1, 675,451 EGD games). The *label* map is linear by decree and holds. The *win-probability* value of a rank is not: **37 Elo-points per rank at 13k, 71 at 1k, 96 at 1d, 214 at 6d** — ~5× wider at the top. "±100 ≈ one rank" is right at 1d and ~2.5× too generous at 10k. |
| 1 | New players at 30k / unrated? | **Co-estimate with downweighting, no waiting period.** Glicko's `g(φ)` already downweights by opponent uncertainty. Seed the prior from Go Diagnostics. Exclude high-RD solvers only from the *puzzle-side* update, never from the player side. |
| 2 | Per-puzzle-type player ratings? | **One global rating plus shrunk per-tag offsets — never independent per-tag pools.** Run the Feinberg–Wainer break-even test on their own log before shipping any per-tag number. |
| 3 | Use time-to-solve? | **Yes, but as a scale anchor and a data-hygiene filter, not as an accuracy fix.** Budget a 10–30 % improvement, not a 2–3× one. Time on correct first attempts only. |
| 4 | Same system for head-to-head games, or Elo? | **Same system. Elo is measurably worse — on Go data specifically.** Fold PvP into one pool with a hierarchical base-skill + per-activity offset. PvP edges are the highest-value fix for the gating penalty. |
| 5 | Average discipline ratings into an overall? | **No — fit the overall directly from all attempts.** Averaging separately-shrunk components over-regresses the aggregate. Blend for *display*, with a per-player, per-tag, sample-size-dependent weight. |

---

## 1. The scale: what one rank is actually worth

**This must be stated explicitly in [`FINDINGS.md`](FINDINGS.md) before any claim about "compression" means anything.**

> **Provenance note.** Unlike the rest of this brief, this section is not a literature summary. The
> tables below are a **primary measurement** taken from the European Go Database's own published
> statistics — 675,451 even tournament games (1996–2025), a 1,052,934-game calibration table, and
> the 4,983-player active ladder, retrieved 2026-09-01. The earlier version of this section compared
> four published mappings against each other and concluded that the literature could not be
> reconciled; measuring it turned out to be cheaper than arbitrating it.
>
> **Every number below is reproduced by [`src/egd_scale.py`](../src/egd_scale.py)**, which re-fetches
> the source tables and reprints this section's tables end to end. `--selftest` checks the
> arithmetic without touching the network and runs in CI. Method and caveats are at the end of the
> section.

### Short answer

Two different things are called "100 points per rank", and only the first one is true.

- **As a label**, one rank is 100 rating points everywhere, by decree — and the ladder obeys it.
  Fitted slope on 4,983 active EGF players: **101.4** GoR/rank over 20k–11k, **97.2** over 10k–1k,
  **99.5** over 1d–7d.
- **As win probability**, one rank is not a fixed quantity at all. Measured over 675,451 even
  games, one rank is worth **37 Elo-400 points at 13k, 71 at 1k, 96 at 1d, 127 at 4d and 214 at
  6d** — about **5× wider at the top of the amateur range than in the middle of the kyu range**.

The crossover, where one rank is worth ~100 Elo-400 points and this repo's flat 400-point scale
constant is exactly right, sits at **1k/1d**. That is not a coincidence: it is the level at which
amateur rating systems were calibrated.

The mechanism is that Go's ranks are a *handicap* ladder. One rank means "one stone makes it fair"
— a fixed quantity of compensation, not a fixed probability. Elo assumes the opposite. The two
agree only if performance noise is constant across levels, and it is not: weak players are
erratic and throw away a one-stone edge, strong players convert it. Same nominal gap, double the
decisiveness.

### The measurement

Win rate of the **stronger** player in even games across one declared grade, pooled over eleven
EGD query windows spanning 1996–2025. 95% Wilson intervals.

| rank | games | stronger player wins (95% CI) | Elo-400 points per rank | EGF-2021 | OGS | AGA |
|---|---|---|---|---|---|---|
| **18k** | 6,049 | 59.3% [58.1, 60.5] | **65** [57, 74] | 55.9% | 55.6% | 82.8% |
| **15k** | 7,427 | 57.6% [56.5, 58.7] | **53** [45, 61] | 56.6% | 56.3% | 82.8% |
| **13k** | 7,345 | 55.3% [54.2, 56.5] | **37** [29, 45] | 57.1% | 56.9% | 82.8% |
| **10k** | 11,289 | 56.3% [55.4, 57.2] | **44** [38, 50] | 58.1% | 57.8% | 82.8% |
| **7k** | 14,447 | 55.7% [54.9, 56.5] | **40** [34, 45] | 59.4% | 58.9% | 82.8% |
| **5k** | 18,713 | 56.7% [56.0, 57.4] | **47** [42, 52] | 60.5% | 59.7% | 82.8% |
| **3k** | 19,790 | 57.7% [57.0, 58.4] | **54** [49, 59] | 61.8% | 60.5% | 82.8% |
| **1k** | 25,909 | 60.0% [59.4, 60.6] | **71** [66, 75] | 63.7% | 61.5% | 82.8% |
| **1d** | 24,596 | 63.5% [62.9, 64.1] | **96** [92, 101] | 64.8% | 62.0% | 82.8% |
| **2d** | 21,288 | 63.4% [62.8, 64.1] | **96** [91, 100] | 66.1% | 62.5% | 82.8% |
| **4d** | 15,062 | 67.5% [66.8, 68.3] | **127** [121, 133] | 69.5% | 63.5% | 82.8% |
| **5d** | 10,421 | 71.3% [70.4, 72.2] | **158** [151, 166] | 71.8% | 64.1% | 82.8% |
| **6d** | 3,561 | 77.4% [76.0, 78.7] | **214** [200, 227] | 74.6% | 64.7% | 82.8% |

The **20k row is excluded** as a floor artefact: it reads 70.9% against 61.8% at 19k, sharply
off-trend, because EGF's rating floor was set at 20 kyu and everything weaker piles into that
label. Labelle and Kaniuk independently discard everything below ~12k for the same reason. Go
Magic's bottom tier sits exactly there, which is a limitation of *any* federation-anchored scale
for this project, not a defect of this measurement.

**Cross-check against a published source.** Kaniuk (2011) reports from the same EGD tables that a
4k beats a 2k 35% of the time and a 2d beats a 4d 22%. This pipeline gives **35.4%** (n = 10,087)
and **22.0%** (n = 12,325) on the pooled window.

### Scoring the four published mappings

Game-weighted mean absolute error against the pooled data, grades 18k–6d, gaps 1–4:

| | overall | 18k–10k | 9k–1k | 1d–6d |
|---|---|---|---|---|
| **EGF 2021** (`β(r) = −7·ln(3300−r)`) | **3.21 pp** | **2.72** | 4.30 | **1.65** |
| **OGS** (`525·exp(rank_idx/23.15)`) | 3.28 pp | 2.76 | **3.00** | 4.27 |
| EGF legacy (pre-2021) | 12.78 pp | 11.93 | 15.05 | 9.38 |
| AGA (`Φ(Δ/1.0568)`) | 23.87 pp | 28.22 | 26.17 | 15.78 |

EGF-2021 and OGS are close overall and split by region: **OGS is better through the single-digit
kyu range, EGF-2021 is much better at dan**, where OGS's curve flattens out and predicts 64.7% at
6d against 77.4% measured. Below 10k they are indistinguishable (2.72 vs 2.76). The legacy EGF curve — still the one quoted by
[Wikipedia](https://en.wikipedia.org/wiki/Go_ranks_and_ratings) as "71.3% for 1k vs 2k" — is off by
13 pp, and **AGA's 83% is off by 24 pp against 675,451 games.**

A second fit worth noting: François Labelle fitted [his own curve](https://wismuth.com/elo/calculator.html)
to EGF's 2006–2015 statistics — `d(Elo)/d(GoR) ∝ (3300 − r)^−1.09`, against EGF-2021's effective
`(3300 − r)^−1` — and the two agree to within 7% across the entire amateur range (38 vs 36
Elo/rank at 20k, 101 vs 103 at 1d, 174 vs 186 at 6d). His motivation was the same as the
Commission's: he calls the legacy EGF curve "not ambitious enough and… not a good fit to the EGF's
own winning statistics."

**Do not present this as independent corroboration.** Both curves use the same 3300 anchor, both
are fitted to the same EGD games, and Labelle's page was last revised in 2021 — the year of the
EGF revision — so which direction the 3300 travelled cannot be established from the public record.
(His superseded formula, still commented out in the source, used 3700.) It is one measurement fitted
twice, which is weaker than it looks: exactly the failure mode §7.3 warns about for OGS-vs-EGF.

### The rating scale is not the lossy part — the rank labels are

EGD also publishes a calibration table binning games by *model-predicted* `Se` and reporting the
observed win rate. Pooled over the same windows — **1,052,934 games, 20 bins** — EGF-2021's
game-weighted mean absolute calibration error is **0.75 percentage points**, with no bin off by
more than 1.8.

That is the distinction that makes the whole literature coherent:

- **rating → win probability** is a solved problem, calibrated to under one percentage point;
- **rank → win probability** is where the information is lost, because a rank label is a
  quantised, noisy, level-dependent projection of the rating.

The size of that loss is measurable on the ladder. Standard deviation of GoR *within* a single
declared grade: **121 points at 20k, 95 at 10k, 45 at 1k, 50 at 1d, 41 at 3d.** A "15k" label
carries about ±1 rank of real information; a "3d" label about ±0.4. The same table shows mild
grade inflation — declared grades sit **10–19 GoR above** the holder's actual rating through the
middle of the range.

This also explains why the measured kyu-range numbers above are *flatter* than EGF-2021 predicts
(55–58% observed against 56–62% modelled): the measurement is taken in grade-label space, where
noise pulls outcomes toward 50%, while the model is calibrated in rating space. Both numbers are
correct and they answer different questions. **Quote the grade-space numbers for what a rank label
delivers; quote the rating-space curve for what the underlying scale is.**

### The three mappings, with sources

**EGF (2021, Bradley–Terry on a log-transformed rating)** — [current system doc](https://europeangodatabase.eu/docs/about/egf-rating-system)

```
Se = 1 / (1 + exp(β(r₂) − β(r₁))),   β(r) = −7·ln(3300 − r)
local logistic scale  a_eff = (3300 − r)/7
con = ((3300 − r)/200)^1.6 ,  bonus = ln(1 + e^((2300 − r)/80))/5
```

Labels are linear by decree: 100 GoR per grade, 20k = 100, 1k = 2000, 1d = 2100, floor −900. The
revision was not cosmetic — the [EGF Rating System Commission](https://www.eurogofed.org/egf/rating_system_commission.html)
(2019–20, convenor Toby Manning) recommended new parameters explicitly *"to more accurately reflect
the probability of winning against players of different strengths"*, and recommended moving the
floor from 20 kyu to 30 kyu. The whole database back to 1996 was recalculated.

**OGS (Glicko-2, exponential rank map)** — [rank_utils.ts](https://raw.githubusercontent.com/online-go/online-go.com/main/src/lib/rank_utils.ts), [glicko2.py](https://raw.githubusercontent.com/online-go/goratings/master/goratings/math/glicko2.py)

```
rating(rank_idx) = 525 · exp(rank_idx / 23.15),   rank_idx = 30 − kyu
```

30k = 525, 20k = 809, 10k = 1246, 1k = 1837, 1d = 1918. Each rank is a constant *ratio* (+4.41%),
so points per rank run 23 at 30k → 36 at 20k → 55 at 10k → 85 at 1d; the 30k→1d span is **1,393
Glicko points, not 3,000**. The Glicko-2 layer uses the vanilla 400-point logistic
(`GLICKO2_SCALE = 173.7178`), so the exponential rank map *is* the mechanism encoding Go's
rank-dependent scale. Two caveats: `MinRank = 5` floors the displayed rank at 25k, so anything
below is extrapolation; and the pre-2021 constants were **A = 850, C = 31.25**, not the figures
that circulate.

**AGA (BayRate, probit, one rank = one stone)** — [game.cpp](https://raw.githubusercontent.com/usgo/AGA-Ratings-Program/master/game.cpp), [aga-rating.txt](https://ffg.jeudego.org/echelle/aga-rating.txt)

`P = Φ(Δ/σ_px)` with `σ_px = 1.0649 − 0.0021976·komi + 0.00014984·komi²` → 82.8% per rank at every
level. The AGA doc states that σ_px "was chosen … to be consistent with the model that the rating
point equivalent of an n stone handicap is 100n" — an **imposed assumption, not a fit**, which is
why it is the outlier. It should not be treated as a competing measurement.

### Recommendation

1. **Declare the scale in [`FINDINGS.md`](FINDINGS.md)** (done — see its scale table).
2. **Keep EGF's linear labels for display** — they are what a Go audience reads, and the ladder
   confirms they hold to within 3 points per rank.
3. **Do not treat 100 points as a constant amount of skill.** For converting this repo's RMSE
   figures into ranks, use the measured curve: **~40 points per rank through the kyu range, ~96 at
   1d, 127+ above it.** "±100 points ≈ one rank" is a dan-calibrated statement and is roughly
   **2.5× too generous at 10k**, which is where Go Magic's catalogue actually lives.
4. **If a likelihood ever needs a Go-realistic link**, carry `a_eff = (3300 − r)/7` rather than a
   flat 400; that is the best-supported curve at dan level and within ~3 pp elsewhere.

Earlier drafts of this section recommended adopting OGS's exponential map outright. The
measurement does not support that as a blanket choice: OGS is the better fit below 1k and
materially worse above it. The reason to prefer OGS's *shape* — exponential, not linear — stands.

### Not transferable to puzzles, except in shape

None of this transfers to *puzzle* difficulty semantically. Puzzles are not players; "one stone"
has no meaning for a tsumego. What transfers is the **shape**: difficulty spacing should be roughly
exponential in rank, not linear. And what is settled for handicap between players —
one stone ≈ 12.5–16.5 points of territory, measured by KataGo ([Nordic Go Dojo](https://www.nordicgodojo.eu/post/8/table-values-of-handicap-stone-settings):
first stone 6.3, then 15.2, 13.5, 16.5, 12.5, 15.5, 12.5, 16.0, 14.5) — has no puzzle analogue at
all.

### What is now settled, and what is not

**Settled by the measurement above:**

- One rank is not a constant number of rating points. The curve rises ~5× from mid-kyu to 6d.
- AGA's 83%-per-rank is wrong for amateur play by 24 pp and is an assumption rather than a fit.
- The legacy EGF curve, still the most-cited figure on the public web, is wrong by 13 pp.
- EGF-2021 predicts real outcomes from *ratings* to within 0.75 pp over a million games.

**Tested here and refuted:** that grade-label noise explains the gap between measured (~60%) and
handicap-anchored (~83%) figures. Correcting the observed win rates for the measured within-grade
GoR scatter, by Gauss–Hermite quadrature over the label noise, moves the implied Elo-per-rank by
only **2–4 points**. Worse, the implied value *rises* with gap size (at 1d: 96 from one-grade gaps,
118 from four-grade gaps) — the opposite sign from what attenuation predicts. The convexity is real
and, if anything, understated. This was previously listed here as a plausible reconciliation; it is
not one.

**Genuinely still unsettled:**

1. **The handicap-stone tension.** Mori's regression discontinuity on 895,050 KGS games
   ([arXiv:1606.05778](https://arxiv.org/abs/1606.05778)) measures one stone at ~30 percentage
   points, implying ~80% — yet one *rank* measures 55–64% across the amateur range. Both cannot be
   right if one rank = one stone. The EGD handicap tables narrow it: pooling the same windows,
   when the handicap **equals** the grade difference — the nominally fair setting — the weaker
   player wins only **40.0%** (44,250 games; 41% at one stone falling monotonically to 35% at
   nine). So one stone per rank systematically **under**-compensates, by roughly half a stone,
   which is the correction Go folklore has always claimed. That reduces the tension but does not
   close it, and the first "stone" (sen, worth ~6.3 points against ~14.5 for later ones) confounds
   the smallest and best-populated cell.
2. **Whether EGF and OGS agreeing below 1k means anything.** They are not independent: OGS's stated
   design goal was "to align our low dan ranks to be comparable to the EGF and AGA low dan ranks."
   The agreement is best where both have least data.
3. **Everything below 12 kyu.** Three independent analysts discard it. EGD's floor artefact makes
   the 20k label uninterpretable, and the Commission's own recommendation to move the floor to 30k
   was a political decision left to the AGM. There is no trustworthy public measurement of the
   30k–12k range — which is precisely Go Magic's first tier.

### Method, and how to reproduce it

```sh
./src/egd_scale.py --selftest   # the arithmetic and the parser, no network
./src/egd_scale.py              # re-derive every table above (~12 min cold, then cached)
```

- **Even-game win rates**: `winning_stats.php?mode=Ajax&From=YYYY-MM-DD&To=YYYY-MM-DD` on
  `europeangodatabase.eu`, which renders EGD's published "Winning Statistics — Even Games" table
  (weaker player's wins and games, by declared grade and by grade gap 1–4). Queried in eleven
  windows covering 1996–2025 — the server times out on the full range — and summed. Totals:
  675,451 even games in the grade-gap tables, 1,052,934 in the `Se`-binned calibration tables.
- **Ladder**: `createalleuro3.php?country=**&dgob=false`, the all-European active list, 4,983
  players with declared grade and current GoR.
- **Conversions**: Elo-400 points from a win rate `p` as `400·log₁₀(p/(1−p))`; Wilson intervals for
  the win-rate CIs, propagated through that transform.
- **One implementation trap**, guarded by a test: ranks are contiguous but their *names* are not —
  there is no "0 kyu" between 1k and 1d. Every gap calculation runs on a contiguous index. Getting
  this wrong corrupts exactly one row in twenty, the 1k row, which is the row the whole "100 points
  per rank" convention is anchored to.

**Caveats that bound every number in this section.**

- The ladder correlation (r = 0.99 overall, 0.95–0.97 within a 10-rank band) is **partly
  circular**: EGD initialises a new player's rating from their declared grade, and several national
  federations assign grades from GoR. It measures bookkeeping consistency as much as reality. The
  *scatter* and the *slope* are still informative; the correlation coefficient on its own is not.
- Grade gaps are declared-grade gaps, so all grade-space figures are attenuated relative to true
  strength gaps. Sizes given above.
- This is European tournament play only: slow time controls, a self-selected population, and a
  grade culture that differs from AGA's and from online servers'.

---

## 2. Cold start: brand-new players

### Short answer

**Neither a waiting period nor exclusion. Co-estimate with an informative prior, and let Glicko's built-in uncertainty weighting do the downweighting — it already does.** The only place to hard-exclude is the *puzzle-side* update.

### Reasoning

Glicko's `g(φ) = 1/√(1 + 3φ²/π²)` takes the **opponent's** deviation and enters the information term squared. So a brand-new player already contributes only a fraction of a settled opponent's information, automatically, with no extra code:

| Opponent RD | 0 | 45 | 75 | 110 | 150 | 200 | 230 | 300 | 350 | 500 |
|---|---|---|---|---|---|---|---|---|---|---|
| `g(φ)²` | 1.000 | 0.980 | 0.946 | 0.891 | 0.815 | 0.713 | 0.652 | 0.525 | 0.448 | 0.284 |

Glickman states the design intent explicitly: "opponents of players with large RDs tend not to be impacted much by the game results against such players" ([glicko-boost.pdf](https://www.glicko.net/glicko/glicko-boost.pdf)), and "in the Glicko system, rating changes are not balanced as they usually are in the Elo system" ([glicko.pdf](https://www.glicko.net/glicko/glicko.pdf)).

So the cold-start problem is **not "who to exclude" but "what prior to give."** Every serious system supplies an informative one:

- **USCF** (maintained by Glickman) imputes an age-based prior and weights external evidence in explicit "games' worth of information" units capped at 10 pseudo-games, then runs a **two-pass** fit — Step 4 computes intermediate ratings, Step 5 re-rates against them ([rating.system.pdf](https://www.glicko.net/ratings/rating.system.pdf)).
- **Glicko-Boost** goes further and *fits* the cold-start prior as a system parameter. Its optimizer chose `r_unr = 1946.25` and `RD_unr = RD₃₀ = RD₂₉ = 250.0`, noting "the initial RD did not seem to depend on whether the player was unrated." Both numbers differ from the 1500/350 default — a concrete argument that Go Magic should fit their prior rather than assume it.
- **Coulom's WHR** adds "one virtual win and one virtual loss against a virtual player of rating zero, on the day of the first game" ([WHR.pdf](https://www.remi-coulom.fr/WHR/WHR.pdf)).
- **FIDE** adds two hypothetical 1800-rated opponents scored as draws ([Handbook B.02](https://handbook.fide.com/chapter/B022024)).
- **Duolingo's production CAT** integrates over item-parameter uncertainty rather than excluding: "items with greater parameter uncertainty have less impact on scores … preventing cold-start items from distorting ability estimates" ([arXiv 2606.07364](https://arxiv.org/html/2606.07364v1)). *(An earlier draft of this research quoted a phrase "all responses contribute to scoring; no exclusions" — that sentence does not appear in the paper and must not be used.)*

The formal argument against conditioning item estimates on person point-estimates is the **incidental-parameters problem**: because the number of ability parameters grows with sample size, JML item estimates are not consistent, whereas marginal maximum likelihood (Bock & Aitkin 1981) integrates ability out. That is the rigorous version of "downweight/integrate, don't exclude."

### The direct precedent: Lichess's asymmetric rule

[`PuzzleFinisher.scala`](https://raw.githubusercontent.com/lichess-org/lila/master/modules/puzzle/src/main/PuzzleFinisher.scala) — verified in production source:

```scala
def puzzle(angle, win, glicko, player) =
  if player.clueless then glicko._1          // RD >= 230: puzzle rating unchanged
  else glicko._1.average(glicko._2, weightOf(angle, win))

def player(angle, win, glicko, puzzle) =
  val provisionalPuzzle = puzzle.provisional.yes.so:
    if win.yes then -0.2f else -0.7f          // provisional puzzle damps player update
  glicko._1.average(glicko._2, (weightOf(angle,win) + provisionalPuzzle).atLeast(0.1f))
```

Plus `RateLimit[UserId](300, 1.day)` — one user can influence at most 300 puzzle ratings per day — and a ±700 clamp on the puzzle delta. Constants from [`Glicko.scala`](https://raw.githubusercontent.com/lichess-org/lila/master/modules/rating/src/main/Glicko.scala): default 1500, `maxDeviation = 500`, `minDeviation = 45`, `defaultVolatility = 0.09`, `provisionalDeviation = 110`, `cluelessDeviation = 230`, `Tau.default = 0.75`, `periodsPerDay = 0.21436` ("chosen so a typical player's RD goes from 60 → 110 in 1 year").

The asymmetry is the insight: **item estimates are the durable deliverable, player estimates are cheap and revisable.** There is no principled derivation anywhere for RD ≥ 230 — it is an engineering constant. Present it as production practice, not as a result.

### Methods to name

Empirical-Bayes / hierarchical prior; Bock–Aitkin marginal maximum likelihood; USCF two-pass ("Glicko-Boost double update"); Coulom virtual-game prior; Glicko `g(φ)` opponent-uncertainty attenuation; fixed-parameter (anchor) linking.

### Implementation

**(a) Seed new players from Go Diagnostics, not from 1500/350.** This is the highest-value recommendation available, because Go Magic already owns the instrument and isn't using it as a prior. Set the initial RD from the diagnostic's own measurement error rather than a constant.

The arithmetic, corrected: from `SE = 1/√Σ P(1−P)` at well-targeted P = 0.5, items needed `L = 4/SE²`, so **`SE = 2/√L`** (an earlier draft had `4/√L`, which is wrong and understates the payoff ~3×). A 15–20 item diagnostic gives SE ≈ 0.45–0.52 logits → **RD ≈ 78–90**, not 160–175. Seeding at RD 87 instead of RD 350 is worth **~15 well-targeted attempts** of information, computed as `(1/φ_t² − 1/φ_0²)/0.25`. Conversion: 1 logit = 173.7178 rating points, so SE 0.3 logits = RD 52.

**(b) Add the Lichess asymmetry to the simulation and *measure* it.** Skip the puzzle-side update when the player's RD ≥ 230; damp the player-side update when the puzzle is provisional. Report the delta on RMSE and slope. Either result is publishable: "we tested Lichess's rule and it moved the number by X" is a far stronger work-sample line than restating the rule. The `g(φ)²` table suggests the built-in 0.448× attenuation may already handle most of it.

**(c) Use different uncertainty budgets for puzzles and players.** Pelánek: "In educational applications there is often an asymmetry in the number of available answers for items and students … It may thus be useful to use different uncertainty function for items and for students" ([CAE-elo.pdf](https://www.fi.muni.cz/~xpelanek/publications/CAE-elo.pdf)). Urnings does the same, with learner urns n = 20 vs item urns n = 204 "because their urnings are updated more often than those of the learners" ([PMC9796260](https://pmc.ncbi.nlm.nih.gov/articles/PMC9796260/)). In Glicko-2 terms: lower `minDeviation` and lower τ for puzzles (static difficulty warrants no volatility), higher τ plus RD inflation over time for players (they genuinely learn).

**(d) Publish difficulty only above a confidence bar**, stated in logits so it's comparable to CAT practice: RD < 52 (SE 0.3, reliability ≈ 0.9) → publish and let it override the hand label; RD < 87 → internal use for selection, hand label stays visible; RD ≥ 110 → hand label only. Volume backing from Linacre ([rmt74m](https://www.rasch.org/rmt/rmt74m.htm)): 50 well-targeted responses for ±½ logit at 95 %, 250 for high-stakes. Across 10,160 puzzles that's ~508k first attempts for "usable" and ~2.5M for "authoritative" — a number Go Magic can check against their log immediately.

**(e) Never let RD hit zero.** Glickman: "I would therefore recommend that an RD never drop below a threshold value, such as 30, so that ratings can change appreciably even in a relatively short time." Lichess uses 45.

**(f) Note the matchmaking/serving formula differs from the update formula.** For selecting a puzzle you want the *combined* deviation: `E = 1/(1 + 10^(−g(√(RDᵢ² + RDⱼ²))(rᵢ − rⱼ)/400))`, whereas the update uses `g(RDⱼ)` alone.

### How long is "cold"?

Derived from Glicko-2's `φ′ = 1/√(1/φ*² + 1/v)` at 0.25 information/game:

| From RD 350 → | 110 | 75 | 52 |
|---|---|---|---|
| vs established opponent | ~9 | ~21 | ~44 |
| vs equally-new opponent | ~20 | ~46 | ~98 |

Two uncertain parties learn from each other at roughly half rate. **These are lower bounds** — they ignore the Step-6 volatility inflation `φ* = √(φ² + σ′²)`, so real convergence is slower. The ~44 figure independently matches the CAT `4/SE²` result for SE 0.3, as it must.

### Caveats

Do not cite specific `dubiousPuzzle` thresholds — the gate exists in Lichess's source (`userApi.dubiousPuzzle(me.userId, perf)`) but its implementation body is unverified, and it reads as anti-sandbagging rather than cold-start handling. On anchor-item share: the frequently-cited ">20 %" figure comes from a paper that actually argues *against* the 20 % rule of thumb, recommending a fit-dependent number instead ([Frontiers 633896](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2021.633896/full)) — cite it as "fit-dependent, and more than 20 % under model misfit."

One honest tension to flag: Bolsinova, Gergely & Brinkhuis (2025, *BJMSP*) find that adaptive selection *plus* simultaneous item updating makes "the variance of the ratings (across persons and items) artificially increase over time and as a result the ratings do not converge" ([PMC12784335](https://pmc.ncbi.nlm.nih.gov/articles/PMC12784335/)) — the **opposite sign** to the 2.3× compression. The reconciliation: their selection is driven by current estimation error (a feedback loop), whereas a skill tree is a static prerequisite graph that bands the matrix without conditioning on estimate error. The contradiction is recorded here rather than dropped, because which sign the distortion takes depends entirely on which selection mechanism a platform actually runs.

---

## 3. Per-skill ratings (life-and-death vs endgame vs tesuji)

### Short answer

**Do not ship independent per-subskill ratings. Ship one global rating plus hierarchically shrunk per-tag offsets — and run the break-even test on their own log before displaying any per-tag number at all.**

### Reasoning: there is a published break-even rule

Feinberg & Wainer (*EM:IP* 33(3), NCME Module 38) give a closed-form screen ([PDF](https://ncme.org/wp-content/uploads/2025/10/Module-38-Subscores-III-Predicting-Subscore-Value.pdf)):

```
Value Added Ratio = 1.15 + 0.51·r1 − 0.67·r2
```

where `r1` = subscore reliability and `r2` = **the disattenuated correlation of the subscore with the remainder of the test** (not with another single subskill — this distinction matters and was gotten wrong in the draft; with a dominant general factor, subscore-vs-remainder runs systematically *higher* than any pairwise tag-tag correlation, so feeding a pairwise number in understates the bar). VAR < 1 → the subscore is worth less than the total score.

Solving for break-even: r2 = 0.70 → need r1 = 0.63; 0.80 → 0.76; 0.85 → 0.82; 0.90 → 0.89; 0.95 → 0.95.

Sinharay ([ED523969](https://files.eric.ed.gov/fulltext/ED523969.pdf)) supplies the empirical bar: "the subscores have to consist of at least 20 items and have to be sufficiently distinct from each other to have any hope of having added value," and "Subscores composed of 10 items were not of any added value even for a realistically extreme (low) disattenuated correlation of 0.7."

**Correction to the folk version:** length and distinctness *trade off*. On Sinharay's own operational table, TB1 (2 subscores, 44 items, disatt 0.90) and TC1 (3 subscores, 68 items, disatt 0.90) each have a subscore with added value. So "added value requires disatt ≤ 0.80" is false — at 0.90 you need ~44+ items; at ~0.78 you need ~25. That trade-off is actually *good* news for a 10,160-puzzle bank with high per-tag volume.

The decisive result for architecture is Haberman's **augmented subscore** — a shrinkage estimator blending the subscore with the total score. It "mostly had added value as long as the disattenuated correlation between the subscores is less than 0.95. Even for a test length of 10, the augmented subscores were found to have added value when the disattenuated correlation was 0.85 or less." That estimator *is* partial pooling. (Haberman's rule adds a qualifier worth keeping: declare added value only if PRMSE_sx is *substantially* larger than both.)

### What the online literature adds

Pelánek's hierarchical Elo ([UMUAI 27:89–118](https://www.fi.muni.cz/~xpelanek/publications/umuai-adaptive-practice.pdf)) is a ~5-line change:

```
P(correct) = σ((θ_l + θ_lc) − d_i)
θ_l  := θ_l  +      U(n_l )·(correct − P)
θ_lc := θ_lc + γ·U(n_lc)·(correct − P)
d_i  := d_i  +      U(n_i )·(P − correct)
```

with `U(n) = a/(1 + b·n)` — fitted `a = 1, b = 0.05` in deployment; `a = 4, b = 0.5` in his simulations (**not** b = 0.05; a tenfold error circulates). γ is the pooling dial; γ = 0 collapses to one global rating.

**The measured gain is small.** Table 1: basic Elo RMSE 0.4142 → hierarchical 0.4115 — ΔRMSE 0.0027, **0.65 % relative**, ΔAUC +0.0083. "The improvement is statistically significant … but it is rather small," and "most predictions (95%) differ by less than 0.1." Abdi et al.'s M-Elo hedges the same way on real data: it beat Elo "but the difference was rather small" ([EDM 2019](https://files.eric.ed.gov/fulltext/ED599177.pdf)).

**Over-splitting measurably hurts.** Table 2: on 1,368 items, 56 concepts (~24 items/concept) gave the best gain (+0.00268); on 39 European countries, 6 concepts (~6.5 items/concept) gave −0.00024. "A model with too small concepts suffers from a loss of information."

**The real argument for hierarchy is robustness, not accuracy.** Pelánek built two 6,000-learner test sets by IP geolocation: "the hierarchical and network model has the same performance on both data sets, whereas the basic model struggles with the heterogeneous data set." A gated skill tree *manufactures* profile heterogeneity — a player who has unlocked life-and-death but not endgame is a different profile. That is the transferable argument. (Note the paper reports no numbers for this comparison; it is a qualitative result carrying a load-bearing claim.)

### Lichess: copy the product surface exactly

Lichess maintains **exactly one** Glicko-2 puzzle rating and renders per-theme numbers as a gated descriptive breakdown ([PuzzleDashboard.scala](https://raw.githubusercontent.com/lichess-org/lila/master/modules/puzzle/src/main/PuzzleDashboard.scala)):

```scala
lazy val performance = puzzleRatingAvg - 500 + math.round(1000 * (firstWins.toFloat / nb))
```

Gates: a theme must exceed `global.nb / 40` of your attempts; weak themes need `failed >= 3`, strong need `firstWins >= 3`; `topThemesNb = 8`; and an explicit insufficient-data state `clear = nb >= 6 && firstWins >= 2 && failed >= 2`. Structural tags (mateIn1..5, short/long, eval tags) are excluded from the breakdown entirely — only genuine motifs appear.

Note `firstWins`, not `wins`. Go Magic's 1–2 "lives" mechanic means this must be computed on first attempts only.

### The finding most likely to be new to them: tag-name leakage

Lichess **down-weights the rating update when a user practises a named motif theme**, because the theme label leaks the solution ([PuzzleFinisher.scala](https://raw.githubusercontent.com/lichess-org/lila/master/modules/puzzle/src/main/PuzzleFinisher.scala)):

| Training angle | Weight on win | on loss |
|---|---|---|
| mix (all themes) | 1.0 | 1.0 |
| `isObvious` (mateIn1, castling, enPassant, doubleCheck, attackingF2F7, all mates) | 0.1 | 0.4 |
| `isHinting` (all motif themes — fork, pin, skewer…) | 0.2 | 0.7 |
| `nonHintingThemes` | 0.7 | 0.8 |

And `nonHintingThemes` is exactly the **game-phase and opponent-strength set**: opening, middlegame, endgame, rookEndgame, bishopEndgame, pawnEndgame, knightEndgame, queenEndgame, queenRookEndgame, master, masterVsMaster, superGM.

That maps cleanly onto Go Magic's grid: the **phase axis** {Opening, Middle Game, Endgame} is non-hinting and safe; the **type axis** {Life & Death, Tesuji, Fighting, Analysis, Knowledge} is hinting — telling a player "this is life & death" leaks that the goal is to kill or live. Any per-tag rating built from tag-filtered practice is therefore measuring an *easier task* than the same puzzle in the mix. A per-tag rating bakes that artefact in; a global rating largely averages it out. The same `ponder` weighting is applied to the puzzle side too, not just the player.

### Implementation

1. **Implement hierarchical Elo** as above. Initialise every `θ_tag = 0` so a player with no data in a tag inherits the global rating — that *is* the shrinkage, and it makes cold start correct by construction. Fit γ by grid search on held-out log-likelihood.
2. **Compute the break-even number rather than asserting an answer.** Get `r2` (tag vs *all other attempts*, disattenuated) from the log; get `r1` empirically via **Bolsinova's parallel-Elo trick** — run two chains on odd/even attempts, select items using one while updating the other, and take `corr(θ̂⁰, θ̂¹)` as split-half reliability. Standard Elo cannot produce a reliability estimate; this one can, and it simultaneously fixes the variance-inflation bug that adaptive-plus-simultaneous-calibration settings are prone to. Convergence cost: hitting times 512.2 responses (parallel Elo) vs 456.1 (Urnings) vs ~100 (standard non-adaptive Elo).
3. **State the prediction, then falsify it.** Go subskills are all "read a board position," so disattenuated correlations will plausibly land near SAT-Verbal's *internal* subscores (0.95, no added value) rather than SAT Verbal-vs-Math (0.76, added value) — especially because a 30k–1d population makes a single rank factor dominate. Falsifiable from their log in an afternoon.
4. **Copy Lichess's display gates verbatim** for the product surface.

### Caveats

**No published measurements of Go subskill correlations exist.** Every quantitative expectation here is transferred from analogous domains. This is the key unknown and must be measured.

The Haberman/Sinharay/Feinberg–Wainer framework is classical test theory for *fixed-length, single-administration* tests where every examinee sees the same items. A gated, self-selected attempt stream breaks two assumptions: the "remainder score" isn't independent of the subscore when practice is tag-filtered (biasing r2), and reliability isn't a fixed test property when attempt counts vary. Apply VAR per-cohort with measured r1; never assume it.

Deep knowledge tracing is not a safe upgrade path. pyKT ([arXiv 2206.11460](https://arxiv.org/pdf/2206.11460)) benchmarked 10 DLKT implementations over 7 datasets and found the *between-paper* AUC spread for a single model on a single dataset (DKT 0.73–0.821; AKT 0.747–0.835) exceeds the typical claimed improvement of a new model over its baseline. simpleKT — a deliberately stripped-down variant — "almost always ranks top 3" against 12 baselines ([arXiv 2302.06881](https://arxiv.org/pdf/2302.06881)). And neither produces an interpretable per-skill rating scale, which is the actual product requirement.

On compensatory vs non-compensatory MIRT: the misspecification literature ([arXiv 2507.15222](https://arxiv.org/pdf/2507.15222)) finds skill bias under misspecification but concludes that variance distortion "does not emerge as a critical concern," and — decisively for Go — that "when two skills are correlated, the compensatory and non-compensatory models yield more similar results." In the high-correlation regime expected here, the worry largely dissolves. Use the compensatory model.

---

## 4. Time-to-solve

### Short answer

**Yes — and there is a large, mature literature. But frame it as a fix for the *scale* problem and a data-hygiene win, not as an accuracy rescue. Budget 10–30 %, not 2–3×.**

### The user's intuition is a named, published model

"A 10k solves a 5k problem in 15 min; a 5k needs under a minute" is **exactly Roskam's (1987/1997) model**, in which log-time is literally additive to log-ability ([PMC7422729](https://pmc.ncbi.nlm.nih.gov/articles/PMC7422729/)):

```
P(Y=1 | T, θ, δ) = θ·T / (θ·T + δ) = σ(ξ + τ − κ),   ξ=ln θ, τ=ln T, κ=ln δ
```

Only the product θ·T matters, so a time ratio *r* is worth `400·log10(r)` rating points. A 15× ratio = 2.71 logits = 470 Elo = **~4.7 ranks** at the ~100-points-per-rank convention, against an intuited 5-rank (10k→5k) gap. Other calibration points: 2× = 1.2 ranks, 5× = 2.8, 10× = 4.0, 30× = 5.9. *(This arithmetic is ours, not a published result, and rests on two approximate conventions. Present it as an illustrative calibration.)*

Roskam has a known flaw: as T → ∞, P → 1 "no matter how difficult the item is." Use Wang & Hanson's asymptote form, `p = c + (1−c)/(1 + exp[−1.7a(θ − b − η·d/T)])`, or the hierarchical model — not raw Roskam.

The intuition is also **empirically confirmed**. Goldhammer et al. (2014, German PIAAC field test, N = 1,020) find the time-on-task effect in problem solving is positive (β₁ = +0.56, z = 2.30, p = .02) and grows stronger on harder items (Cor(b0i, b1i) = **−.61**) and for weaker persons (Cor(b0p, b1p) = **−.79**) ([PDF](https://www.pedocs.de/volltexte/2019/17967/pdf/Goldhammer_etal_2014_time_on_task_effect_in_reading_and_problem_solving_A.pdf)). The −.79 is precisely the intuition: extra time buys a weak player much more than a strong one. Note this is domain-specific — in *reading* (routine/automatic processing) β₁ = −0.61.

### Why raw time is not simply "more information"

van der Linden's driving analogy ([2011 chapter, PDF](https://www.psychologie-aktuell.com/fileadmin/download/ptam/3-2011_20110927/05_vanderLinden.pdf)): equating raw RT with speed "would be the same error as asking our colleagues how long it takes them to drive to work, and then conclude that the one with the shortest time drives fastest. The missing factor, of course, is the distance driven." Distance = item labor intensity.

Worse, the speed-accuracy tradeoff "is a within-person relationship" while all you observe is between-person data, so "the results can be a positive, negative or zero correlation between speed and ability." Hence the deliberately provocative conclusion: "in somewhat of an ironic twist, the speed-accuracy tradeoff actually forces us to **ignore** the relationship between speed and ability when modeling responses and RTs." Pelánek labels the same trap "a special case of Simpson's paradox" ([UMUAI 2024](https://www.fi.muni.cz/~xpelanek/publications/umuai-response-times.pdf)).

### Method to use: van der Linden's hierarchical model

```
Level 1 (RT):        ln t_ij = β_i − τ_j + ε,   ε ~ N(0, α_i⁻²)
Level 1 (accuracy):  standard IRT / Bradley-Terry, CONDITIONALLY INDEPENDENT of RT given (θ, τ)
Level 2:             (θ, τ) ~ MVN(μ, Σ_θτ);  item params ~ MVN(μ, Σ)
```

β_i = time intensity, α_i = time discrimination (the *inverse* SD of log-RT), τ_j = person speed.

**The load-bearing argument for this project**, verbatim from the source: "β_i − τ_j is the mean of the log RT on the item, but θ_j − b_i is not the mean response"; and because ln t is measured in seconds, the RT model's parameters have "a scale with a fixed unit; we only need one additional constraint to fix its arbitrary zero," whereas the response model "has both an arbitrary unit and origin."

**Time intensity is an externally-anchored ruler that banded pairing cannot compress the way it compresses the logit scale.** That is the strongest reason to collect response times, and it holds independently of whether they improve accuracy.

Two reinforcing facts. Conditioning on time gives ~**20 % MSE reduction** on difficulty parameters b_i at ρ_θτ = .75, N = 300 — and "the reduction is larger than the average exactly where it is most needed, toward the two ends of the scale." And the mechanism directly attacks shrinkage: the RT-based per-item prior "avoids the typical bias toward the location of a common prior in traditional item calibration."

For *ability* estimation there are closed-form update equations — no MCMC at serve time — and "a 10-item adaptive test with the use of RTs and a correlation between ability and speed equal to .6 yields similarly accurate estimates of θ as a 20-item version without the use of RTs."

### The hard ceiling

Ranger (2013, *Psychometrika* 78(3):538–544): "It can be shown that the consideration of response times increases the information of the test. However, one also can prove that the contribution of the response times to the test information is bounded and has a simple limit." ([Cambridge Core](https://www.cambridge.org/core/journals/psychometrika/article/abs/note-on-the-hierarchical-model-for-responses-and-response-times-in-tests-of-van-der-linden-2007/277756A9786127B19A39F318608CA52E))

The mechanism: RTs inform θ *only* through τ, so the maximum possible gain is what you'd get if τ were observed exactly — which does not grow with test length. The commonly quoted `ρ²/(1−ρ²)` bound is **not attributable to Ranger** from anything retrievable (the abstract doesn't state it; full text paywalled), though it is the mathematically natural limit: if τ were known, θ's conditional prior variance is 1−ρ², so added information is `1/(1−ρ²) − 1`. Present it as a derivable heuristic, not as Ranger's result. Likewise "10–30 %" appears in no source — it is an order-of-magnitude expectation extrapolated from one 20 % simulation figure.

**This is the single most important counterweight to the hope that time might rescue the 2.3× compression. It won't.**

### Directly transferable evidence from chess

van der Maas & Wagenmakers (2005), Amsterdam Chess Test ([PDF](https://www.ejwagenmakers.com/2005/VanderMaasWagenmakersACTpaper.pdf)) introduce **CISRT** = Σᵢ Accᵢ·(MT − tᵢ) — bank the leftover time, but only on items you got right.

- At the **item** level, mean improvement in correlation with Elo over plain accuracy = **+.11** (t = 2.18, df = 157.9, p < .05, over 80 items).
- That improvement correlates **r = .78** (N = 80, p < .001) with item *easiness* — "the advantage of using the speed–accuracy CISRT measure was more pronounced for the easy items."
- The decisive asymmetry: mean RT on **correct** responses correlates with Elo at r = −.30 and −.26 (p < .001); on **incorrect** responses at −.02 and −.11 (both n.s.).

**Honest qualifier:** at the whole-test level the gain is marginal — accuracy r(Elo) = .78 vs CISRT .79 on test A, .81 vs .81 on test B, significant for only one of the two (Z = 1.69). The impressive result is at the item level, which *is* the right level for difficulty estimation, but "beat plain accuracy" overstates the test-level picture.

Implication for Go Magic: time carries signal only on successes, and it earns its keep precisely where accuracy saturates at ceiling — which inside a gated skill-tree band is most items.

### What the platforms actually do

**Lichess uses no time at all in puzzle rating** — verified by reading production code, not documentation. `PuzzleFinisher.scala` computes both ratings from the boolean win/loss only; response time appears nowhere. Only the first attempt counts (`prev.updateWithWin(win)`), which maps exactly onto Go Magic's lives mechanic.

**Chess.com uses time only to modulate the player's reward** via a "Target Time" speed bonus, and — the most product-relevant fact here — **freezes puzzle difficulty after calibration**: "When a puzzle is first added, its rating is determined by who is able to solve it. After a set period, the puzzle's rating becomes locked and does not change further" ([support article 8602396](https://support.chess.com/en/articles/8602396-how-do-puzzle-ratings-work) — note this is a *different* article from the general "How do Puzzles work" page). Chess.com re-rated every player and puzzle in October 2025, so date any description. Whether the speed bonus touches the *puzzle's* rating is not stated and cannot be settled — Chess.com is closed-source.

**Lichess Puzzle Storm is explicitly unrated**: "Puzzle Storm is unrated. And when you review a puzzle from a storm session, it also is unrated" ([lichess.org/page/storm](https://lichess.org/page/storm)).

Both platforms independently quarantine speed-pressured play from difficulty estimates, because under time pressure the speed-accuracy tradeoff is being deliberately manipulated.

### Implementation, in priority order

1. **Ship the cheap win first: data hygiene.** Rapid-guessing filtering via Wise & Kong's **Response Time Effort** ([ED490203](https://files.eric.ed.gov/fulltext/ED490203.pdf)): `SB_ij = 1 if RT_ij ≥ T_i`, `RTE_j = (Σ SB_ij)/k`. Their thresholds were set from item surface features (<200 chars → 3s; >1000 chars → 10s; else 5s). Validation: α = .97, correlations with SAT subscales "near zero" (it measures effort, not ability), accuracy on rapid-guess responses did not exceed chance. Use Pelánek's transform `f(t) = log2(t/median_item)` — **median, never mean**: "Mean response times should not be used," and split-half reliability shows median RT becomes highly reliable at a few hundred answers per item while mean RT "improves only slightly with additional data." Because Go Magic has **no timer today**, censor the *upper* tail too (idle tabs) — an untimed log has a contaminated right tail as well as a rapid-guess left tail. Goldhammer's precedent: log-transform, then winsorize beyond 2 SD (~4.7 % of cases).
2. **Add the lognormal layer to the existing joint/batch MAP fit.** Couple to accuracy only through a level-2 covariance — do *not* put time in the level-1 likelihood; conditional independence is the whole design. Report recovered β_i against known ground truth and show whether the 2.3× compression shrinks. Clean, falsifiable extension of the experiment already in the repo.
3. **Use time only on correct first attempts.** Wrong-answer time is noise (r = −.02/−.11, n.s.).
4. **Validate on real data before claiming anything about Go.** The `AmsterdamChess` dataset in the **LNIRT** R package ([CRAN ref](https://search.r-project.org/CRAN/refmans/LNIRT/html/AmsterdamChess.html)) is 259 players × 40 chess problems with `Y1–Y40`, `RT1–RT40` in seconds, and external `ELO` — rated players solving rated puzzles against the clock, with ground truth attached. LNIRT fits exactly the van der Linden model, so the method can be demonstrated end-to-end in an afternoon.
5. **Use Go Diagnostics to fit the population covariance Σ_θτ**, then carry it as the prior into the gated pool. It is the one place where θ and τ can be estimated free of the banded design.
6. **Propose the guardrail unprompted.** Go Magic lists "Timed Mode SOON — Solving against the clock is coming soon" ([gomagic.org/go-problems](https://gomagic.org/go-problems/)). Recommend that timed attempts update a *separate* rating and never feed canonical difficulty estimates. Both major chess platforms independently made that call.

Also available if you want to separate "how hard the item is" from "how careful this player is being": **EZ-diffusion** (Wagenmakers, van der Maas & Grasman 2007) gives closed-form drift rate, boundary separation and non-decision time from just Pc, MRT and VRT of correct responses. Note the drift formula uses a **fourth root**, not the square root rendered on mathematicalpsychology.com — verified by numerically round-tripping the forward diffusion equations (the fourth root recovers all parameters to 4 decimals; the square root fails). Caveat: EZ is extremely sensitive to outlier RTs, which in an untimed learning app is a serious concern.

### Genuinely unsettled

Pelánek's own conclusion (§7.5): "At the moment, it is not clear how to effectively use response time in student modeling." The difficulty-estimation and disengagement-detection applications are far better established than the ability-estimation one — fortunate, since this project targets difficulty recovery. And the whole hierarchical framework assumes constant speed and ability *within a session*; van der Linden treats violations as test-design flaws. A self-paced learning app is the opposite of a controlled test session.

**No Go-specific literature exists.** Every quantitative result here is transferred from chess or general psychometrics. The chess transfer is well-supported; the Go transfer is an assumption to state explicitly rather than to lean on silently.

---

## 5. Head-to-head games: same system, or Elo?

### Short answer

**Same system. Elo is not on the table — it is measurably the worst option, benchmarked on Go data specifically.** Fold PvP into the *same pool* with a hierarchical base-skill + per-activity offset, and treat it as the highest-value structural fix for the gating penalty.

### Elo is last

Coulom (2008) benchmarked six systems on KGS Go games: training 726,648 even/komi-6.5 games (2000–2005), test **2,331,757** games (2005–2007) ([WHR.pdf](https://www.remi-coulom.fr/WHR/WHR.pdf)):

| System | Test prediction | CPU (training) |
|---|---|---|
| Elo (k=20) | 55.121 % | 0.41 s |
| Glicko | 55.522 % | 0.73 s |
| TrueSkill | 55.536 % | 0.40 s |
| Bayeselo | 55.671 % | 88.66 s |
| Decayed history | 55.698 % | — |
| **WHR** | **55.793 %** | 252.00 s |

95 % confidence of superiority requires a 0.091 % gap. Elo-vs-Glicko (0.401 %) clears it comfortably; **Glicko-vs-TrueSkill (0.014 %) does not**, so do not rank them against each other.

### The real answer is the graph, not the update rule

Bradley–Terry estimation is governed by the **connectivity of the comparison graph**. Ford's (1957) condition: "In every possible partition of the items into two nonempty subsets, some item in the first set has beaten another in the second set." When it fails, "no amount of data will be able to resolve the ranking between any two items belonging to different groups, and the model is non-identifiable. As a result, the MLE does not exist" (Bong & Rinaldo, [ICML 2022](https://proceedings.mlr.press/v162/bong22a/bong22a.pdf), Theorem 3.2: if λ₂(I*) ≥ 2 log d / n then P[Ford's condition fails] ≤ 2/√d; Theorem 4.1 gives the estimation-error bound).

**This is the formal statement of "the gating penalty does not wash out with volume."** A gated skill tree is a near-block-diagonal graph: λ₂ is small, so the *scale* between tiers is weakly determined even as within-tier ordering becomes near-perfect (Spearman 0.95). Adding volume *inside* blocks does not raise λ₂. *(The paper's main results assume a connected graph, so the gated-tree reading is our extension of their motivating counterexample, not their theorem. Say so.)*

Coulom states the same pathology in plain language: "if two players, A and B, enter the rating system at the same time and play many games against each other, and none against established opponents, then their relative strength will be correctly estimated, but not their strength with respect to the other players" — and if A later plays established opponents, B's rating *should* change, "But incremental rating systems would leave B's rating unchanged."

**Player-vs-player games are the highest-value edges Go Magic can add**, because two humans of different tiers play each other while two puzzles in different tiers never meet a common solver.

### Merging is what the field does

- **WHR** *is* the batch/joint MAP fit — a dynamic Bradley–Terry model that "directly computes the exact maximum a posteriori over the whole rating history of all players." Validated on Go. Scale: 213,426 players, 10.8M games, **~7 minutes** for 200 Newton iterations on a 2007-era Core2 Duo. A joint refit of a corpus 1000× larger than Go Magic's runs in minutes.
- **The AGA's official system** is the same idea: "For multiple games, the RPs for all the players, and the PXs for all the games, are multiplied together to obtain the overall likelihood… The maximum Bayesian likelihood is found numerically by simultaneously adjusting all the ratings" (px_sigma = 104, rp_sigma = 80).
- **KGS** also fits by maximum likelihood across recent games rather than incrementally.
- **Chess.com** replayed "about 17 billion" puzzle attempts to re-rate every player and puzzle ([announcement](https://www.chess.com/news/view/announcing-new-puzzles-rating-system)) — global batch refits of both sides are operationally normal at scale.

So the 63 % batch-fit advantage is not exotic; it has two Go-native precedents. The cheap middle path Glickman himself uses is the **USCF / Glicko-Boost two-pass update**: rate once, then re-rate against the opponents' post-first-pass ratings. It captures part of the joint-fit gain at near-online cost and is a far easier sell to an engineering team than "rewrite as a batch optimizer."

**Suggested architecture: online Glicko-2 for live player-facing ratings; nightly joint MAP refit for canonical puzzle difficulties.**

### One pool or two? The trait question

TrueSkill2 (Minka, Cleven & Zaykov, [MSR-TR-2018-8](https://www.microsoft.com/en-us/research/wp-content/uploads/2018/03/trueskill2.pdf)) solves exactly this in production. They measured the correlation between a player's skill in two Halo 5 modes at **r = 0.6**, and found "A player's skill in any gameplay mode is positively correlated with their skill in all other modes." Rather than a full covariance matrix, they use one shared dimension:

```
skill_id(t) = base_i(t) + offset_id(t)
base_i(t0) ~ N(0, v_b);  offset_id(t0) ~ N(m_d, v_d);  each with its own drift
```

The stated failure of the naive alternative: "The traditional approach… is to have a separate skill distribution for each mode. This is equivalent to assuming that a person's skill in one mode is independent of their skill in another mode."

**How large is the shared factor for puzzles vs play?** Evidence is two-sided:

- 5,000+ Lichess players: R² = 0.48 (r ≈ 0.69) between puzzle and game ratings, with a regression **slope of 0.62** — "if you compare two players with 100 points difference in tactics rating, the higher rated player will tend to have 62 higher classical chess rating." Community analysis, author-flagged selection bias.
- Amsterdam Chess Test (259 participants, 215 with official Elo): choose-a-move correlated **.77 and .81** with Elo — the highest of any subtest. Stepwise regression on all six ACT scores explained **70 %** of Elo variance. But Elo and tournament performance rating correlate only r = .88 with each other, which effectively **caps achievable criterion validity**.

So: a large shared factor exists, but decisively not r = 1, and the *scales* are not 1:1 even between two well-populated pools measuring the same people.

Both chess platforms rate puzzles with the same algorithm as games but keep a **separate scale**, deliberately aligned rather than merged. Chess.com's 2025 overhaul deflated the puzzle scale hard (a mate-in-one fell 1800 → 963) so that "Your Puzzles rating should still be higher than rapid and blitz, but it should be much closer now."

And Go Magic has already published the cautious position: "your estimated puzzle rank may differ from your actual playing rank — solving and playing are related but separate skills" ([gomagic.org/go-tests](https://gomagic.org/go-tests/)). The design should agree with it.

### Implementation

1. **One pool, one joint fit.** Glicko-2 online; joint MAP as source of truth.
2. **Model each player as `base_i + offset_i^activity`.** One latent strength anchors both activities; one learned offset absorbs the systematic puzzle-vs-play gap. Report two user-facing numbers. `m_d` is *estimated*, not assumed.
3. **Ship a falsification test before merging.** Fit puzzle and play scales separately on players active in both, then regress one on the other. Slope ≈ 1 with tight residuals justifies a shared base skill; a slope like Lichess's 0.62 with wide residuals says keep the offset (and possibly a per-activity slope). Report the number either way.
4. **Handicap is an additive rating offset**, in every major Go system. OGS: `E = 1/(1 + exp(−g()·(rating_self + handicap_adjustment − rating_white)/173.7178))`, computed in *rank* space first ("Note that the 'rating' domain is log-scale, where +/- is asymmetric"). AGA: `100·stones − 10·komi` for 2 ≤ stones ≤ 9, and `50 − 10·komi` when **stones = 0** (an even game with komi — not, as often misstated, a one-stone case). EGF reduces the gap by `100·(H − 0.5)`. KGS subtracts 1 rank per stone. Pick a convention explicitly; the first "stone" (sen/no-komi) is worth only ~6.3 points versus ~14.5 for subsequent ones.
5. **Fix the rating periods rather than the algorithm.** Glickman: Glicko-2 "works best when the number of games in a rating period is moderate to large, say an average of at least 10-15 games per player." OGS knowingly violates this — "each rating period has exactly one game in it" — and documents the damage: "Every period looks to Glicko-2 like an 'outlier'"; deviation stays high; recency bias; deviation fails to grow during inactivity ([RatingsV6.md](https://raw.githubusercontent.com/online-go/goratings/master/RatingsV6.md)). **A puzzle app can satisfy the 10–15 rule** — solving sessions batch naturally, unlike an ad-hoc game server. That is a cheaper win than switching algorithms.
6. **OGS's multi-pool design is worth copying** for any future split: 16 ratings (overall + 3 speeds + 3 board sizes + 9 combinations), where non-overall categories take the *opponent's* rating and deviation from the well-connected "overall" pool. They also record the failure mode of unlinked pools: forum regulars keep multiple accounts as a workaround.

### Confront Pelánek head-on

Pelánek's simulation found that under *adaptive* item selection, proportion-correct fails badly and "the quality of these estimates moreover does not improve with the increasing number of students" — but "The Elo rating system… gives nearly the same estimates as joint maximum likelihood." That superficially contradicts the 63 % joint-fit advantage. The reconciliation: his adaptive selection still lets every student span the full difficulty range, whereas tier gating **hard-partitions the graph** (small λ₂). Naming this shows you read the literature rather than cited it.

### Caveats

**No Go server runs WHR on its main ladder.** WHR was *developed and validated on* Go data (KGS); KGS and AGA use their own ML fits, OGS uses Glicko-2. Don't say "WHR is the Go system."

**No paper studies the actual question** — joint estimation of item-response (puzzle) data and head-to-head (game) data in one pool. The IRT concurrent-vs-separate calibration literature is the nearest analogue and is genuinely unsettled. The recommendation here is an engineering synthesis, not a citation, which is why it ships with a falsification test.

**"Go Diagnostics is ungated" is a hypothesis, not a verified fact.** The public page never says this. The entire anchor-set recommendation depends on it — verify against their DB.

TrueSkill Through Time reports *log-evidence*, not predictive accuracy, so the widely-repeated "TTT beats TrueSkill by X %" framing is unsupported by the paper's own numbers. And TrueSkill2's 68 %-vs-52 % is on Halo 5 team games with rich in-game features, not a clean read on the base+offset mechanism alone.

---

## 6. Averaging discipline ratings into an overall

### Short answer

**Do not compose the overall rating by averaging shrunken per-tag ratings. Fit the overall directly from all attempts, and use blending only for the per-tag *display*.** Every production system blends rather than choosing — but the fixed weights used in tennis are an approximation, not a principle.

### The tennis evidence: blending strictly beats choosing

Jeff Sackmann uses a flat **50/50** mix of surface-specific and overall Elo. His benchmark on ~50,000 ATP matches ([Heavy Topspin](https://www.tennisabstract.com/blog/2017/06/23/unpredictable-bounces-predictable-results/)):

| Surface | Overall Elo (Brier) | Surface Elo | **50/50 blend** |
|---|---|---|---|
| Hard | .205 | .202 | **.202** (acc 68.6 % vs 68.5 %) |
| **Clay** | **.211** | **.213** | **.207** |
| **Grass** | .207 | .207 | **.196** |

**On clay, pure surface-specific Elo is *worse* than pure overall Elo — and the blend beats both.** That single row is the most persuasive artifact in this entire literature. (Precision: on hard court the blend ties on Brier and wins only on accuracy. It strictly beats both on clay and grass.)

On weight choice, Sackmann tested "a wide range of possible mixes" and found "the differences between, say, 60/40 and 50/50 are extremely small on all surfaces." FiveThirtyEight, on the same sport with different data, landed on a *different* fixed weight: "0.71 · overall Elo + 0.29 · surface Elo" for hard courts ([Wayback](https://web.archive.org/web/2018id_/https://fivethirtyeight.com/features/how-were-forecasting-the-2016-us-open/)). **The two disagree by a factor of ~1.7 on the specialised estimate and neither explains the gap** — which is itself evidence that the optimum is broad and flat, not that 50/50 is a transferable constant.

### The principle underneath: one formula, four names

The weight on a specialised estimate should be `n/(n + k)` with `k = (within-discipline noise variance)/(between-discipline true variance)`:

- **Bühlmann credibility**: `Z = n/(n+K)`, `K = EPV/VHM` ([Loss Data Analytics ch. 9](https://openacttexts.github.io/Loss-Data-Analytics/ChapCredibility.html))
- **Gelman BDA3 eq. 5.17**: `θ̂_j = [(1/σ_j²)ȳ_.j + (1/τ²)μ] / [1/σ_j² + 1/τ²]` — "a precision-weighted average of the prior population mean and the sample mean of the jth group." Substituting σ_j² = σ²/n_j gives exactly n/(n+k) with k = σ²/τ².
- **James–Stein / empirical Bayes**: Efron & Morris's baseball example estimated `(k−3)/V = .791`, i.e. **only 21 % weight on the individual estimate at n = 45** — equivalent to k ≈ 170 at-bats. Total squared prediction error fell from 17.56 to 5.01 (efficiency 3.50), better for 15 of 18 batters.
- **Ridge / RAPM**: Sill (MIT Sloan 2010) — "The λ in the equation corresponds to the ratio of the variance of the inherent, unpredictable noise to the variance of this gaussian prior," chosen by 10-fold CV and reported back in interpretable prior-SD units (λ = 3000 ↔ prior SD 2.71).

**k must be measured per discipline, never assumed.** Tango's published baseball constants in exactly the x/(x+PA) form span more than 26×: HR x = 131, SO x = 62, RBOE x = 1627. "It's all based on comparing the observed variance to the expected variance based on luck, and attributing the difference to the true variance" ([tangotiger.net](https://tangotiger.net/archives/stud0274.shtml)).

### The decisive warning for this question

Tango, verbatim: **"By keeping the components separate, you overstate the OVERALL regression, while correctly stating the component regression."** Components each regressed 40 % at 600 PA imply ~30 % regression for the aggregate, not 40 %.

**So: fit the overall rating directly from all attempts. Never average the 15 shrunken per-tag ratings to produce it.**

### Joint update, not per-tag independent updates

This is the second decisive result. Vermeiren, Hofman & Bolsinova ([EDM 2025](https://educationaldatamining.org/EDM2025/proceedings/2025.EDM.long-papers.99/2025.EDM.long-papers.99.pdf)) compare:

- **MERS**: `θ_im(t) = θ_im(t−1) + a_jm·K(X − E(X))` using the **joint** multidimensional expectation
- **MELO**: updates each skill using only that skill's *unidimensional* expectation plus a zero-sum normaliser

Finding: "the MELO and the unidimensional ERS exhibited mostly inward bias… individuals with abilities above the average are systematically underestimated… while those below average are overestimated," and "the magnitude of bias for the MELO increased as the absolute true ability values became larger." MERS shows only small *outward* bias, near-perfect rank correlation regardless of inter-skill correlation, and robustness to Q-matrix (tag-matrix) misspecification. Prediction MSE over the final 800 games: MERS 0.148856, MELO 0.150366, unidimensional 0.151623.

**Inward bias is scale compression — exactly the failure this project already measured at 2.3×.** Adopting a MELO-style per-tag update would be a second, self-inflicted source of it. Note also the paper's honest headline: MELO converges faster but "exhibits significant bias and lower prediction accuracy compared to the MERS." And the absolute MSE gap between all three is tiny (0.1489 vs 0.1516) — multidimensionality buys ~1.8 % even with three genuinely distinct simulated dimensions.

### The item side

Kandemir, Vie et al. ([LAK '24, arXiv 2403.07908](https://arxiv.org/pdf/2403.07908)) contribute the piece Go Magic needs on the item side: **separate item difficulty from tag difficulty**.

```
λ_ui = (1/δ) Σ_k θ_us_k          # mean learner ability over the δ tags on item i
μ_i  = d_i + (1/δ) Σ_k θ_s_k     # item difficulty PLUS mean tag difficulty
P    = σ(λ_ui − μ_i)
```

with `U(n) = a/(1 + bn)`, a = 1, b = 0.5, plus a **floor of 0.03 so ratings never freeze** ("this lower bound applies after 65 attempts"). Reported ~73.7 % accuracy, 0.81 AUC on a production corpus of 357,317 questions, 31 specialties, 26.8M attempts, sparsity 0.99.

**Important:** borrow only their `d_i` / `θ_s` *difficulty split*. Their **ability** update is MELO-style — the paper says so explicitly ("the prediction formula operates at the specialty level for each tagged specialty, just like in [Abdi]") — i.e. the design EDM 2025 shows produces inward bias. Graft the difficulty split onto a MERS-style joint ability update, and say that you are doing so.

### Implementation

**Parameterise the hierarchy, don't build two systems:**

```
Puzzle difficulty:  d_p = μ + t_{tag(p)} + e_p,        e_p ~ N(0, σ_e²)
Player skill:       θ_{u,g} = θ_u + δ_{u,g},           δ_{u,g} ~ N(0, σ_tag²)
Overall rating:     θ_u, fitted directly from ALL attempts
Displayed per-tag:  θ̂_u + w_g · δ̂_{u,g}
```

For a puzzle carrying tags G, predict `σ(Σ_{g∈G} a_g θ_{u,g} − d_p)` with Σ a_g = 1, then update every tag in G with weight a_g times the **same joint residual**.

**On the blend weight `w_g` — three cautions:**

1. `w_g = σ_tag²/(σ_tag² + Var(δ̂_{u,g}))`, and `Var(δ̂_{u,g})` is **not** simply RD_g². It is `Var(θ̂_{u,g}) + Var(θ̂_u) − 2Cov`, and the covariance is not small when the same attempts feed both. Using RD_g² alone is valid only if θ̂_u is treated as known.
2. **Units.** Glicko-2 RD is on the Glicko scale; divide by 173.7178 to get logits before mixing with a logit-scale variance component.
3. **Rename the between-tag SD.** Glicko-2 already reserves τ for its volatility system constant (typically 0.3–1.2), and the numeric coincidence with a plausible between-tag SD of ~0.3 logits makes the collision hard to catch. Call it `σ_tag`.

The textbook `n/(n+k)` form: near p = 0.5 a Bernoulli attempt carries Fisher information 0.25 in logit units, so Var ≈ 4/n and `k = 4/σ_tag²`. **This degrades exactly in the regime gating pushes you into** — inside a tier, players mostly solve, so effective information per attempt is below 0.25, the true k is *larger*, and you should shrink harder than the formula suggests.

Estimate σ_tag by Tango's method of moments — observed variance of raw per-tag deviations minus mean sampling variance — and **publish the number**. Do not guess it. For scale intuition only: Ingram's hierarchical tennis model puts surface-specific skill SD at 0.067 against overall skill SD ~0.14–0.154, i.e. discipline deviation SD ≈ half the overall SD, with clay preference ranging from +0.16 (Nadal) to −0.11 (Becker) ([PDF](https://martiningram.github.io/papers/bayes_point_based.pdf)). If Go tags behave similarly and σ_tag ≈ 0.3 logits (~52 Elo points), then k ≈ 44 attempts — you hit 50/50 at ~44 attempts per tag. **That is why tennis's flat 50/50 works at typical career volumes and why it would be badly wrong for a user with 5 attempts on a tag.** It is an analogy, not a measurement.

**Validate the way Sackmann did, and publish the table.** On held-out attempts, report accuracy / Brier / log-loss for four estimators: overall-only, per-tag-only, fixed 50/50, and the σ_tag-derived adaptive weight. Reproducing the shape of Sackmann's clay row on Go Magic's own data would settle the question directly, which no citation can.

**State of the art, if they want to go further:** Ingram's Bayesian extension of Elo learns the full covariance matrix between disciplines via steady-state Kalman filtering, so a result in one discipline propagates into correlated ones automatically — a learned, per-player, uncertainty-aware blend rather than a hand-set constant. Reference implementation: [jax_elo](https://github.com/martiningram/jax_elo), `models/correlated_skills_model.py`. Blending is the special case.

### Caveats

**No source makes the tennis blend weight sample-size dependent.** Both Sackmann and FiveThirtyEight use a single constant for all players regardless of matches played. The `n/(n+k)` machinery is fully established in credibility theory, empirical Bayes, Marcel, and RAPM — but nobody has applied it to surface Elo. The per-player recommendation is a cross-field synthesis, not a citation.

**The "15 concept tags" figure used in the k ≈ 44 illustration is a placeholder** — it is not sourced from Go Magic's data. Confirm the actual tag taxonomy before any tag-count-derived number appears in the deliverable.

**Tag identity is likely confounded with skill-tree tier.** If some tags appear predominantly in 30–18k and others in 9–1k, a tag-level difficulty offset will absorb tier effects and the hierarchical prior will propagate that confound into every puzzle in the tag. Check the tag × tier cross-tabulation before fitting, and consider an explicit tier term so the tag term is estimated *within*-tier. No source addresses this; it is specific to Go Magic's design.

---

## 7. What the literature does not settle

These should be stated wherever the recommendations are, not glossed: each one bounds how far the recommendation above it can be carried.

1. ~~**What one Go rank is worth in win probability.**~~ **Now measured — see §1.** 55–58 % through the kyu range, 63.5 % at 1d, 77 % at 6d, over 675,451 EGD games. AGA's 83 % is wrong for amateur play by 24 pp and was an imposed assumption rather than a fit; the legacy-EGF 71–72 % figure still quoted on Wikipedia is wrong by 13 pp. What *remains* unsettled is the sub-12k range, where no trustworthy public measurement exists — and that is Go Magic's first tier.
2. **The handicap-stone tension.** Mori's regression discontinuity on 895,050 KGS games measures one stone at ~30 percentage points, implying ~80 % — yet §1 measures one *rank* at 55–64 % across the amateur range. Both cannot be right if one rank = one stone. §1 narrows the gap: at the nominally fair setting (handicap = grade difference) the weaker player wins only **40.0 %** over 44,250 games, so one stone per rank under-compensates by roughly half a stone. It does not close it. Note that the previously-listed explanation — measurement error attenuating the fitted slopes — has now been **tested and refuted** in §1.
3. **Whether OGS and EGF agreeing on the DDK scale means anything.** They agree to within 1–3pp, but **not independently**: OGS's stated design goal was "to align our low dan ranks to be comparable to the EGF and AGA low dan ranks," and it benchmarks its own handicap win rate directly against EGF's. The agreement is best where both have least data. §1 checked whether Labelle's separate curve breaks the circle and concluded it does not: it lands within 7 % of EGF-2021 but shares the same 3300 anchor and the same underlying games, and the direction of borrowing cannot be established. **Every curve in this literature is fitted to EGD.** A genuinely independent check would need a second federation's raw game records.
4. **The exact RD threshold for excluding a solver from item updates.** RD ≥ 230 is a Lichess engineering constant with no published derivation anywhere.
5. **Ranger's exact information bound.** The boundedness is proven; the `ρ²/(1−ρ²)` formula is derivable but not attributable.
6. **Whether puzzle-solving is compensatory or non-compensatory in Go.** The misspecification literature's own recommendation is to decide on substantive theory rather than fit indices — and notes the two models converge when skills are correlated, which is the expected Go regime.
7. **Whether parallel Elo or Urnings is preferable** for adaptive-with-on-the-fly-calibration. Bolsinova et al. explicitly conclude "more research is needed to pinpoint under which conditions either of the methods should be preferred."
8. **Whether item-response and head-to-head data belong in one joint pool.** No paper studies it. The IRT concurrent-vs-separate calibration literature is the nearest analogue and is mixed.
9. **Go subskill correlations, Go puzzle↔play correlation, and Go response-time effects are all unmeasured.** Every number transferred here is from chess or general psychometrics. Go Magic's own DB could produce the first such measurements — which is an opportunity, but the transfer must be stated as an assumption, not assumed.

One claim to actively avoid: the **Urnings** algorithm is often described as correcting "exactly" the distortion this simulation found. It does not. Urnings corrects rating **variance inflation** from error-driven adaptive selection — "the ratings are diverging from each other over time without converging to a limiting distribution." This project measured the **opposite** distortion: scale compression, a too-narrow recovered spread. Describe Urnings as "a related published treatment of pairing-induced rating distortion," never as the same phenomenon.

---

## 8. Suggested build order

Cheapest-and-most-defensible first. Each step is independently reportable.

| # | Step | Cost | Why it earns its place |
|---|---|---|---|
| 1 | **Declare the scale.** *Done.* [`FINDINGS.md`](FINDINGS.md) now carries the measured curve from §1 — EGF labels for display, ~40 points per rank through the kyu range rising to ~96 at 1d — with the tier spans. | done | Nothing downstream means anything without it, and a Go company will check. |
| 2 | **RTE / median-RT data hygiene.** Rapid-guess floor, idle-tab ceiling, `log2(t/median_item)`. | ~1 day | Improves difficulty estimates through preprocessing alone. No new model, and every step is auditable against the raw log. |
| 3 | **Seed player priors from Go Diagnostics** (RD ≈ 80–90 rather than 350) and run the A/B against the flat prior. | ~1 day | Uses a product they already own; worth ~15 attempts of free information per player. |
| 4 | **Add Go Diagnostics items as ungated anchors** to the simulation; sweep the anchor count and plot slope → 1.0. | ~2 days | This directly attacks the λ₂ / scale-compression finding. If a handful of ungated items collapses the 2.36 slope, that is the headline result of the whole repo — and it is an actionable product recommendation, not just a measurement one. |
| 5 | **Add the Lichess asymmetry** (clueless-solver exclusion from puzzle updates; provisional-puzzle damping of player updates) and report the delta. | ~1 day | Either outcome is publishable. |
| 6 | **Simulate PvP edges**: add a small fraction of cross-tier human-vs-human games and plot recovery error against λ₂ of the resulting graph. | ~2 days | Turns the existing finding into a business recommendation, and is the strongest structural argument available. |
| 7 | **Hierarchical per-tag offsets + the Feinberg–Wainer VAR test** (r1 via parallel Elo chains, r2 vs remainder). | ~3 days | Turns "should we?" into a computed number. Expect per-tag-only to lose outright. |
| 8 | **Lognormal RT layer** in the joint MAP fit; validate first on the LNIRT `AmsterdamChess` dataset. | ~3 days | Demonstrating the method on real rated-player puzzle data with ground-truth Elo is far more persuasive than another synthetic run. |
| 9 | **Two-pass (USCF/Glicko-Boost) update** as the production-realistic middle path between online Glicko and full batch. | ~1 day | Much easier to sell to an engineering team than "rewrite as a batch optimizer." |

Two lines worth including verbatim in any write-up, because they read as judgement rather than enthusiasm:

- *"Ranger (2013) proves the information gain from response times is bounded and does not grow with volume. Budget 10–30 %, not a rescue."*
- *"If Timed Mode ships, timed attempts should update a separate rating and must never feed the canonical difficulty estimates — which is what both Lichess and Chess.com independently decided."*

---

# What this brief overstates

A completeness critic reviewed the synthesis above for gaps and overclaims. Its findings are
reproduced verbatim, because several of them matter more than the content they criticise — in
particular the fourth, which prescribes a gate this repo has already measured as unsafe.

**Gaps in the brief (ranked by how much they change the deliverable)**

- **The obvious search never run: does any Go site already rate puzzles by attempts?** Six dossiers cite Lichess and Chess.com; none checks 101weiqi (has a rated tsumego ladder with user-derived difficulty), goproblems.com (user-rated problems since ~2005), or Tsumego Hero. That is the one direct, in-domain precedent — a Go company will ask about it first, and its absence quietly weakens "no Go-specific literature exists" (there may be no *papers*, but there is production practice).
- **Second obvious search not run: engine-derived difficulty.** No search for KataGo/solver-based tsumego difficulty (solution depth, branching factor, policy entropy, value-swing at the key move). This is the only thing that cold-starts all 10,160 puzzles with *zero* traffic, which is precisely the failure mode [`FINDINGS.md`](FINDINGS.md) §7 identifies (median puzzle 22 attempts, hardest 3). Chess's analogue — predicting puzzle rating from features, the Lichess puzzle-difficulty dataset — is also uncited.
- **The free item-side prior is ignored.** The brief argues hard for informative *player* priors (Go Diagnostics, §2a) and never once proposes using Go Magic's existing 11-level hand labels as the informative prior on `d_p`. That reframes the hand label from "thing to replace" to "prior to shrink away from as traffic accrues", handles the starved tail, and is a one-line change to `batch_fit.py`. Biggest missed recommendation in the document.
- **Recommendation 2(d) contradicts the repo's own measurement.** "Publish difficulty when RD < 52 / 87" — but `docs/METHOD.md` §7 and OPEN-QUESTIONS.md already found RD is *not* a safe readiness gate under gating: ~77 points of reported uncertainty against ~287 points of realised error. The brief prescribes exactly the gate the repo flagged as unsafe, with no calibration step. Either drop it or condition it on the ungated instrument's RD.
- **Uneven traffic ([`FINDINGS.md`](FINDINGS.md) §7) appears nowhere in the brief.** The funnel costs 40–50 RMSE points and collapses gated ρ from 0.94 → 0.78 — as expensive as gating itself. Every per-tag recommendation assumes "high per-tag volume for a 10,160-puzzle bank"; under the measured funnel most tags have a starved tail and the Feinberg–Wainer / Sinharay "≥20 items" bar fails for most players. The §3 and §6 recommendations are never re-checked under funnelled traffic.
- **Q6 was answered as a literature question, not as a project question.** *Partly addressed:* §1 is now a measurement rather than a survey, and the scale is declared in [`FINDINGS.md`](FINDINGS.md). But the project question the critique names is still open, and is now sharper rather than softer: on the measured curve the ±100 "one rank" target is ~2.5 ranks at 10k and ~1 rank at 1d, so every rank-denominated figure in [`FINDINGS.md`](FINDINGS.md) is a dan-calibrated lower bound. What remains undecided is whether the planted population and the published tables should be **restated** on the measured curve, and what the 2.36× compression figure becomes in those units. Tracked in [`OPEN-QUESTIONS.md`](OPEN-QUESTIONS.md).
- **"PvP edges are the highest-value fix for the gating penalty" is unsupported and outranked by the repo's own numbers.** Measured fixes: joint refit −61% (free), linking items −57 to −188 RMSE with dose-response. PvP is unmeasured, requires a product Go Magic does not have, and the brief's own §5 build item is 2 days of simulation. Calling it highest-value is an overclaim against measured alternatives.
- **The Ford/Bong–Rinaldo identifiability framing is probably the wrong theorem.** A ±300 band is *banded*, not block-diagonal — adjacent tiers share solvers, so the graph is connected and the MLE exists. The repo confirms this: gated error falls steadily at ~28 points per doubling out to 1,280 attempts. The pathology is ill-conditioning / low Fisher information along the scale direction, not non-identifiability, yet the brief quotes "no amount of data will be able to resolve" verbatim. λ₂ is the right intuition; the citation attached to it is not.
- **Single-weak-source claims that are load-bearing:** (a) the Lichess puzzle↔game slope 0.62 — one community blog post, author-flagged selection bias, no date or primary link — yet it is the concrete number the §5 falsification test is calibrated against; (b) the "10–30 %" RT budget, extrapolated from one 20 % simulation figure (ρ=.75, N=300) and then quoted verbatim as a headline line to include in the write-up; (c) Sackmann's clay row, one blog post with no CIs, called "the most persuasive artifact in this entire literature"; (d) the Nordic Go Dojo blog as the sole source for what the brief calls *settled* about stone value; (e) Mori's unpublished preprint carrying the whole handicap tension.
- **No discrimination or guessing parameter anywhere.** The whole brief (and `batch_fit.py`) is 1PL/Rasch. Go puzzles plausibly vary hugely in discrimination — a life-and-death shape you either see or you don't — and the answer space is small enough that a lower asymptote is real. Discrimination heterogeneity is a known source of exactly the scale distortion being measured, and 2PL/3PL recovery under banded designs is never searched or discussed (only α_i inside the RT model, which is time discrimination, not item discrimination).
- **Two load-bearing data assumptions are unflagged.** The brief flags "Go Diagnostics is ungated" as a hypothesis, but not (a) that per-attempt **timestamps exist and are usable** — the entire §4 is void otherwise, and there is no timer today, so the log's right tail is idle-tab contaminated in an unknown proportion; nor (b) the "millions of attempts already in their database" volume claim the 508k/2.5M feasibility arithmetic rests on, which is unsourced in the repo's own sourcing table.
- **No scoping to the deliverable, and no separation of runnable-today from needs-their-DB.** OPEN-QUESTIONS.md §0 says the output is a one-page PDF, not started. The build order is ~14 days across 9 steps, of which steps 3, 7, and most of 2 require an attempt log nobody outside the company has. The brief never says which one or two items change the one-pager, nor states the decision the difficulty number actually feeds (mislabel-review queue? tree ordering? adaptive serving?) — and the required precision differs by an order of magnitude between them.

---

# Where this contradicts the repo, and which wins

| the brief says | the repo measured | resolution |
|---|---|---|
| Publish difficulty when RD < 52 / 87 (§2d) | Under gating, RD reports ~77 points of uncertainty against ~287 points of realised error ([`METHOD.md`](METHOD.md) §7) | **The repo wins.** An RD threshold is not a safe readiness gate on gated data. Either calibrate RD against realised error on anchor items first, or gate on the *ungated* instrument's RD |
| PvP edges are the highest-value fix for the gating penalty (§5) | Joint refit: −61%, free, measured. Linking items: −57 to −188 RMSE with a dose-response, measured | **The repo wins.** PvP is unmeasured and needs a product that does not exist yet. It is a good idea ranked too highly against measured alternatives |
| Per-tag recommendations assume high per-tag volume across a 10,160-puzzle bank | Under a realistic traffic funnel the median puzzle sees 22 attempts and the hardest 3 ([`FINDINGS.md`](FINDINGS.md) §7) | **Unresolved, and it matters.** The Feinberg–Wainer and Sinharay volume bars were never re-checked under funnelled traffic. Per-tag ratings are likely further off than §3 implies |

---

# Field evidence: two *All Things Go* interviews with Nikola Tsarigradski

Everything above is literature and source code. This section is different: it is what a Go
mathematician says goes wrong on a live Go server running the same estimator this repo implements.
It is the cheapest reality check available on the whole project, and it was found late.

- [S5.15 — PlayGo "Battle of the Sexes" & rating quirks in OGS](https://allthingsgogame.com/2026/07/27/playgo-battle-of-the-sexes-ogs-rating-quirks/) — OGS is the second half
- [Go rating systems: Elo, Glicko, dan/kyu](https://allthingsgogame.com/2026/07/27/go-rating-systems-elo-glicko-dan-kyu-world-tournament/) — the more technical of the two

**Provenance, stated once.** These are the publisher's own transcripts, described as lightly edited
for clarity, read as text rather than heard as audio. The guest says outright that he could not
locate OGS's numerical algorithm and was not reading its source, so his account is *behavioural* —
what the system visibly does — not an implementation audit. Treat the figures below as reported.

## What it confirms

**The information-collapse mechanism, observed in the wild.** On the thin pool of strong players he
notes it is hard to tell whether a strong player is 5, 8 or 10 stones stronger, because they win
nearly every game regardless. That is exactly `g² · E · (1−E)` going to zero — the same quantity
section 3 of `METHOD.md` derives, and the same reason a gated tree cannot fix its scale. Two
independent routes to one conclusion.

**One rank is not a constant win probability.** The second episode states that the dan/kyu system
predicts *handicap fairness*, not win probability, and that the relation is roughly logarithmic:
a 20k beats a 19k about 38% of the time (so the stronger wins ~62%), while a 6d beats a 7d only
about 20% (the stronger wins ~80%).

| one-rank gap | this interview | EGF 2021 model | **measured (§1)** |
|---|---|---|---|
| at high kyu | ~62% | 55.5% | **61.8%** (19k, n = 5,331) |
| at high dan | ~80% | 78.2% | **77.4%** (6d, n = 3,561) |

The interview matches the *measurement* at both ends — within 0.2 points at the kyu end and 2.6 at
the dan end — better than either matches the model. Note the row label: the measured high-kyu
figure is 19k, not 20k, because 20k is EGD's rating floor and reads a spurious 70.9% (§1). The
interviewee's "38% for the weaker player" is very nearly exactly what the 19k data says (38.2%).
A third independent source that **"±100 points ≈ one rank" is dan-calibrated and generous below
it** — and, now, a check that lands on the data rather than on the model.

**Non-transitivity.** Listed as a known limitation: three equally-rated players can form a win
cycle, because style matchups exist and a single latent trait cannot express them. That is the
`FINDINGS.md` limitation "real Go skill is not one-dimensional", stated by someone who models ratings.

## What is new, and what it changes here

**1. OGS is a live cautionary tale for §5's blending recommendation.** OGS holds separate ratings
per format and displays a *traffic-weighted average* of them. The consequence, in the guest's
words, is that it is possible to win a game and lose rating: a win in a format you rarely play
raises both that format's rating and its weight in the average, which can drag the displayed
overall down. Section 5 above concluded, from shrinkage theory, "do not average separately-shrunk
components — fit the overall directly and blend only for display." **This is that failure in
production, in Go.** It applies directly to any per-tag rating Go Magic might show across the 3×5
grid, and it is a far more persuasive argument to a Go audience than James–Stein.

**2. Effort contamination is a real threat to log quality.** He describes being badly underrated —
and accused of sandbagging — purely from playing tired blitz games while distracted. The
simulation assumes one clean latent trait and a well-behaved logistic; a real attempt log contains
low-effort attempts that satisfy neither. This supports two existing positions: the lives mechanic
genuinely suppresses careless clicking (`FINDINGS.md` §6), and response time earns its place as a
*hygiene filter* — rapid-guessing detection — rather than as an accuracy improvement (§4 above).

**3. Rapid improvers contaminate the items they touch.** Named as a known problem: players who
improve faster than the system tracks deflate their opponents. `METHOD.md` §3 already argues that
puzzles do not drift while players do; this is the other direction of that asymmetry, and it is
worse for item calibration, because an improving player's early attempts bias puzzle difficulties
in a direction nothing later corrects.

**4. A concrete motivation for the rating clamp in `OPEN-QUESTIONS.md`.** The guest describes a test account
exploiting handicap: nine stones on a 9×9 against a 25-kyu bot is treated as roughly 45 handicap
stones, so the algorithm infers something like 20 dan; about ten such games, plus deliberate losses
to damp volatility, produced an account displaying 9 dan+ with rating points near 13 dan. lila
clamps ratings to `[400, 4000]` and this repo does not — the open item now has a Go-specific
motivation rather than a chess-specific one. He argues pool-wide damage stays limited because such
accounts lose heavily once they play at their real strength, which is the RD mechanism working.

## Nothing here contradicts a finding of this repo

Worth stating explicitly, because it would be the more interesting outcome. The quirks described
are **product and population** problems — how ratings are aggregated for display, who is in the
pool, how seriously people play — rather than defects in Glicko-2's arithmetic, which is the part
this repo validates against Glickman's worked example.
