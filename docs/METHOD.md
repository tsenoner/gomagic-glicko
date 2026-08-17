# Measuring puzzle difficulty: what, why, and how

A method document for this repo. It assumes you know that Elo exists and that Glicko is supposed
to be an improvement on it. Everything else — rating deviation, volatility, identifiability,
restriction of range, Rasch models, why online and batch fitting differ — is defined here.

**Section 3 is the arithmetic.** It exists so the rest can be trusted, and it can be skipped on a
first read. Sections 5–7 are the actual argument.

---

## 1. Introduction

### The answer, first

Go Magic assigns puzzle difficulty by hand: a static 11-level table, one person's judgement per
puzzle, across 10,160 puzzles, never revised by the attempts already sitting in their database.
The question this repo asks is what it would take to *measure* difficulty instead.

The answer has three parts, and they are more useful than a slogan:

1. **At low volume the difficulty is real and no estimator fixes it.** At 10 first attempts per
   puzzle, a skill-tree-shaped attempt log gives you about 400 rating points of error — four Go
   ranks — and switching to a better estimator buys 5% of it back. That is an information limit in
   the data.
2. **At useful volume most of the penalty is an artefact of how you fit, not what you have.** At
   160 first attempts per puzzle, online Glicko-2 reports 279 points of error where a joint refit
   of *the identical log* reaches 103. That is a 63% cut for nothing but compute.
3. **It does not vanish.** After the refit, gated data is still 1.6× worse than ungated data
   (103 against 63). That residual belongs to the shape of the log and no estimator choice touches
   it.

The single cheapest recommendation that follows: **for a one-off backfill over existing history,
fit jointly, and do not conclude from an online pass that your data is inadequate.** Reserve the
online estimator for the live path, where it is the right tool.

There is also a warning that came out of writing this document, and it is the most operationally
dangerous finding in it: **Glicko's own confidence number is badly over-confident on gated data.**
At 160 attempts per puzzle under gating, the estimator reports a rating deviation of 77 points
while making 279 points of error — it is 3.6× more wrong than it admits. Using RD as a
"is this label ready to ship?" gate, which is the obvious thing to do, would ship confidently
wrong labels. Section 7 has the table.

### What this is not

**This does not claim Go Magic's labels are wrong.** Nobody outside the company can know that;
deciding it means comparing labels against how players actually performed, which needs the private
attempt log. This repo answers the question that comes *before* that one — if you ran the
estimator, how much data would you need before the answer meant anything? — which depends only on
the estimator's behaviour and the *shape* of the data, and can therefore be settled by simulation
with no access to anything.

### The units, once

Everything is on one scale, and it is worth fixing the conversions before any numbers appear.

| | |
|---|---|
| default rating | 1500, for players and puzzles alike |
| the scale constant | 400 points = 10-to-1 odds. A 200-point advantage is a 76% win rate; 400 points is 91% |
| Go ranks | roughly **100 rating points per rank** over the kyu range, so 20k ≈ 700 and 1d ≈ 2100 |
| the accuracy target | **±100 points ≈ one rank.** A label off by 300 points is off by three ranks, which is a different puzzle |

So read every error figure in this document as "how many ranks off is a typical label".

### The two error numbers, once

Ratings have no absolute zero (section 6 explains why), so every error figure requires aligning
the fitted values against the truth first. There are two ways to do that and they answer different
questions. Both are reported everywhere in this repo:

| | what it removes | what it can still see |
|---|---|---|
| **RMSE(off)** | one mean offset | ordering **and** spacing — a compressed scale still counts as error |
| **RMSE(aff)** | a full least-squares affine map | ordering only |
| **slope** | — | the affine scaling factor: 1.0 means the fitted scale is already right, 2.35 means the fitted spread is 2.35× too narrow |

**RMSE(off) is the primary number everywhere.** RMSE(aff) is blind to scale error by construction,
and its alignment is fitted against the answer key, which no production system has. Section 6 is
about why that distinction nearly produced a false conclusion in this repo.

### What the public page already tells us

`src/parse_tree.py` reads the `data-*` attributes off `gomagic.org/go-problems/`. Everything in the
tree's structure is in the server-rendered HTML, so this is reading a public page rather than
reverse-engineering anything:

| | |
|---|---|
| Skill nodes | **74** across 3 tiers: basics 30–18k (20), intermediate 18–10k (25), sdk 9–1k (29) |
| Prerequisite rows | **35** — progression is row-by-row, not a free dependency graph |
| Structure | 1–5 levels per node × 2–6 quizzes per level × 5 puzzles per quiz |
| Attempt slots to complete the tree | **4,790** |
| Hardmode nodes | 23 |
| Concept tags | `{opening, middle-game, endgame}` × `{fighting, tesuji, life-and-death, analysis, knowledge}` |

Two things follow. The 3×5 tag grid is already the vocabulary a difficulty model — or a mistake
classifier — would target; it does not need inventing. And nothing in that markup is a
*measurement*: difficulty is a hand-assigned band per node, which is the gap this repo is about.

### The shape of the problem

The arithmetic that motivates all of this:

- **10,160 puzzles** in the catalogue, carrying **11** hand-assigned difficulty levels.
- The public skill tree has **74 nodes** and **4,790 attempt slots** to complete end to end — so
  walking the entire tree does not reach even half the catalogue once.
- Measuring a puzzle to one-rank accuracy takes on the order of **160 first attempts** on that
  puzzle, ungated. Across the catalogue that is 10,160 × 160 ≈ **1.6 million first attempts**.
- And "160 first attempts on this puzzle" means 160 *distinct players reached it*, not 160 on
  average across the catalogue. Traffic through a prerequisite tree is wildly uneven, so coverage
  will be uneven by construction — which is an argument for a per-puzzle readiness gate rather
  than a global cutover.

That is why the question is "how much data, and shaped how", rather than "which algorithm".

### Sourcing: what can be checked and what cannot

This repo commits an HTML snapshot so results reproduce offline. It does not cover everything the
document asserts about Go Magic, and the difference is worth stating once rather than caveating
repeatedly:

| claim | status |
|---|---|
| the skill-tree inventory below (74 nodes, 35 rows, 4,790 slots, tiers, tags) | **backed** by `data/skilltree-2026-08-16.html`, reproduces exactly |
| "10,160 puzzles" | **backed** — the phrase appears in the snapshot |
| "5 puzzles per quiz" | **backed** — *"a quiz — a short series of 5 puzzles"* |
| the static 11-level difficulty table | **not backed.** The snapshot contains the word "difficulty" zero times |
| the lives mechanic (section 4) | **not backed** — from other, un-snapshotted pages |
| the Go Diagnostics "confidence range" quote (section 7) | **not backed** — same |
| the Lichess constants in `glicko2.py` | **not verified.** Quoted from `lila`'s puzzle-rating code from memory, with no pinned commit or URL. Nothing in the simulation depends on them being exactly right |

### Map

- **Section 2** — Elo, Glicko, Glicko-2: what each adds, and why it matters for puzzles.
- **Section 3** — the Glicko-2 update, step by step, mapped to the code. The arithmetic.
- **Section 4** — the gap between the paper and something you could run on a real database.
- **Section 5** — the experiment: how you test an estimator when you have no ground truth.
- **Section 6** — what "measured" means, and the two ways to be wrong.
- **Section 7** — what the experiment found, and what to do about it.
- **Section 8** — glossary.

Sections 2–4 are the estimator. 5–6 are the method. 7 is the result.

---

## 2. Elo, Glicko, Glicko-2: what each one adds

The core idea that makes any of this possible is worth stating before the lineage: **treat an
attempt as a game.** The player is one competitor, the puzzle is the other; solving is a win for
the player, failing is a win for the puzzle. `src/glicko2.py` makes that literal — there is one
type, used for both sides:

```python
@dataclass
class Rating:
    """A player or a puzzle. Same type on purpose: to the algorithm they are both competitors."""
```

The consequence is the thing a hand-assigned table can never give you: difficulty comes out
**denominated in the same units as skill**. A puzzle at 1300 and a player at 1500 sit on one axis,
so "this player solves this puzzle about three times in four" is immediately available, and at
~100 points per rank the difficulty also translates into the rank vocabulary the site already
speaks. A hand-assigned "level 7 of 11" translates to nothing — you cannot subtract it from a
player's rank and get a probability.

The three rating systems are a chain, each adding exactly one tracked quantity. Elo tracks a
rating. Glicko adds an uncertainty about that rating. Glicko-2 adds an erraticness. The reason to
walk the chain rather than jump to the end is that each addition does a specific job *for this
problem*, and the jobs are easy to conflate if you meet them all at once.

### Elo: rating differences predict outcomes

Elo's single real idea is that you never need a competitor's absolute strength, only that the
*difference* between two ratings maps onto a probability through a fixed curve:

```
E = 1 / (1 + 10 ** ((r_opponent - r_you) / 400))
```

The update rule is `r_new = r_old + K * (S - E)`, where `S` is 1 for a win and 0 for a loss. With
`K = 32` against an opponent 200 points below you (`E = 0.76`), winning moves you +7.7 and losing
moves you −24.3. Expected wins are cheap; unexpected losses are expensive. That asymmetry is the
whole learning mechanism, and Glicko and Glicko-2 both keep it.

Elo then fails in two ways that matter specifically for puzzles.

**K is a single global knob.** Every competitor moves by the same amount per game regardless of
how much is already known about them. A puzzle published this morning with zero attempts and a
puzzle with 5,000 attempts behind it get identical step sizes. One should be sprinting toward its
true value; the other should barely twitch, because one more attempt is a rounding error against
5,000. Elo cannot express the difference, so whatever `K` you pick is wrong for one of them: tune
it up and settled puzzles jitter, tune it down and new puzzles take thousands of attempts to
arrive. For a catalogue of 10,160 puzzles with wildly uneven traffic, that is not a corner case —
it is the whole catalogue.

**Elo has no notion of confidence.** A rating of 1300 from three attempts and a rating of 1300
from three thousand are the same number. For a product that wants to *display* a difficulty, or
gate content on it, or pick someone's next puzzle with it, the question "is this label ready yet?"
has no representation at all. You would bolt on an attempt-count threshold, which is the global
knob again in a different hat.

### Glicko: rating deviation, the uncertainty about the rating

Glicko adds one number per competitor: the **rating deviation** (RD), an uncertainty expressed in
the same units as the rating, so it reads directly as an interval. Glickman's rule of thumb is a
95% interval of rating ± 2·RD. A puzzle at 1300 with RD 45 means "1300, give or take about 90
points — under one rank". At RD 350 it means "1300 is barely a guess", an interval of ±700, seven
ranks.

RD does two entirely distinct jobs, and conflating them is the most common way to misread Glicko.

**Your own RD controls how far you move.** High RD, large steps; low RD, small ones. This is Elo's
`K` replaced by a quantity the system derives from its own state. It is not a subtle effect. Take
a well-measured player at RD 45 solving a puzzle currently rated 1500, and vary only the *puzzle's*
RD:

| puzzle's RD before | rating after | moved by |
|---|---|---|
| 350 (brand new) | 1324.92 | −175.08 |
| 45 (well measured) | 1494.02 | −5.98 |

Same event, same starting rating, steps 29× apart. The new puzzle sprints, the settled one
twitches, and nothing was tuned to produce that.

**Your opponent's RD discounts what their result teaches you.** Beating someone whose rating is
itself a guess tells you little, because you do not know what you beat. Glicko computes a weight
`g` from the *opponent's* RD which shrinks from 1 downward as their uncertainty grows:

| opponent's RD | g |
|---|---|
| 45 (the floor this repo enforces) | 0.990 |
| 100 | 0.953 |
| 150 | 0.903 |
| 350 (a fresh competitor) | 0.669 |
| 500 (the ceiling) | 0.533 |

That weight enters in three places — it flattens the predicted probability toward a coin flip, it
scales how hard the result pushes your rating, and it scales how much certainty you gain. So a
game against a fresh competitor moves you less *and* teaches you less. Section 3 has the formulas.

**RD grows when idle and shrinks as you play.** A rating period with no games holds the rating and
inflates the deviation. Section 3 discusses the tension in applying that to puzzles, which unlike
players do not actually drift.

Glicko does not eliminate every constant — the floors and ceilings in section 4 are all chosen
numbers — but it replaces the constant that sets *how fast every rating learns* with something
derived. That is the real gain.

### Glicko-2: volatility, how erratic the results are

Glicko-2 adds a third number, **volatility** (sigma). RD asks *how unknown is this competitor's
true value*. Volatility asks *how consistent are its results, once you account for that*. They are
different questions and they come apart.

Take two life-and-death puzzles that, after 20 attempts each, sit at the same rating with the same
RD. The first is a plain corner shape: whether you solve it tracks your reading strength almost
monotonically, so its results land where the model expected and the rating settles. The second is
a trick puzzle turning on one throw-in tesuji that you have either seen before or you have not. A
15-kyu who met the motif last week solves it; a 5-kyu who never has fails it. Outcome depends on
*motif exposure*, which is only loosely correlated with strength, so its results keep contradicting
the model in both directions. The rating may average to the same place, but any label printed from
it stands on shakier ground.

Volatility carries that difference, and the structural change it enables is this: **uncertainty can
now grow in response to evidence, not only from the passage of time.** In plain Glicko, RD only
ever shrinks while a competitor is active — a run of results that flatly contradicts the current
rating still makes it look more certain. Glicko-2 lets contradiction re-open the interval.

Running a 10-game rating period from 1500 / RD 100 / volatility 0.06 against ten known opponents:

| the period's results | rating after | RD after | volatility after |
|---|---|---|---|
| 5 wins, 5 losses (exactly as predicted) | 1500.0000 | 74.5907 | 0.059959 |
| 10 wins from 10 (a surprise) | 1658.1665 | 74.5924 | 0.060185 |

The predicted period pushed volatility down, the surprising one pushed it up, and the surprised
competitor came out with marginally more residual uncertainty despite the same number of games.
The magnitudes are deliberately small: volatility is a slow-moving quantity that compounds across
periods rather than lurching within one. **`tau` bounds how fast it may move** — on the same
10-win period, volatility lands at 0.06003 for tau 0.3, 0.06019 for tau 0.75, and 0.06048 for tau
1.2.

This matters for how this repo runs the estimator: `play()` calls `update()` with a one-game list,
so a "rating period" here is a *single attempt*. With periods that short, volatility does
comparatively little work per attempt. Do not expect it to rescue a sparse catalogue.

### Why this machinery suits puzzle difficulty

Beyond the shared scale already described, RD is the piece that repairs Elo's second failure in a
directly usable form. "When is a measured difficulty ready to replace the hand-assigned one?"
becomes a threshold on a number the estimator already maintains per puzzle, rather than a global
attempt count applied to a very non-uniform catalogue. And because RD re-inflates when a puzzle
goes idle or when results start contradicting the model, the readiness check keeps working after
day one.

That is the theory. Section 7 tests it and finds RD is not trustworthy for this job on gated data.

Lichess rates its puzzles this way — puzzle as competitor, Glicko-2 — which is the existence proof
that the approach survives production, and the source of the non-Glickman details in section 4.

### The three side by side

| system | tracks | fixes | still cannot do |
|---|---|---|---|
| **Elo** | rating | Turns rating *differences* into outcome probabilities on a fixed curve, so ratings from different matchups are comparable at all | One global `K`: a 0-attempt and a 5,000-attempt puzzle move identically. No confidence, so no way to say a label is ready. Treats an opponent's rating as fact when it is a guess |
| **Glicko** | + rating deviation | Step size becomes per-competitor and derived rather than tuned. An opponent's RD discounts their result. RD grows while idle, so staleness is visible | While a competitor is active RD only shrinks — results that contradict the rating still make it look more certain. Assumes the true value is stable |
| **Glicko-2** | + volatility | Separates *unknown* from *erratic*. Surprises raise volatility, which inflates RD before the shrink, so uncertainty can grow from evidence. `tau` bounds how fast | Neither the origin nor the spread of the scale is anchored by anything. And no version recovers differences the comparison data never contained: if players only meet puzzles near their own level, the spacings are weakly constrained no matter how good the estimator is |

That last cell is the pivot into the rest of this document. The machinery is sound; what it
produces depends entirely on the shape of the log you feed it.

---

## 3. The Glicko-2 update, step by step

This section maps Glickman's eight steps onto `src/glicko2.py`. Every worked number below comes
from the example printed in his paper: a competitor at 1500 / RD 200 / volatility 0.06 plays three
opponents, beating the first and losing to the other two, with tau = 0.5.

| Glickman's step | produces | where |
|---|---|---|
| 1–2 | conversion to the internal scale (mu, phi) | `Rating.mu`, `Rating.phi` |
| 3 | `v` — the variance the games imply | the accumulation loop in `update()` |
| 4 | `delta` — the move the games alone suggest | `delta = v * delta_sum` |
| 5 | `sigma_prime` — the new volatility | `_new_volatility()` |
| 6 | `phi_star` — deviation inflated by volatility | `phi_star = sqrt(phi**2 + sigma_prime**2)` |
| 7 | `phi_prime`, `mu_prime` — the new deviation and rating | two lines below that |
| 8 | conversion back, and the clamps | `_clamped(...)` |

### Steps 1–2: the internal scale

Glicko-2's algebra is logistic, and logistic algebra is clean in natural-log units. The
1500-centred 400-point Elo scale is those same units multiplied by a constant, so the algorithm
converts once in and once out:

```python
SCALE = 400.0 / math.log(10.0)     # = 173.7178
```

Nothing about it is tunable — it is the 400-point convention expressed in natural-log units.
`batch_fit.py` imports `SCALE` from this module rather than writing `400/ln(10)` again, so the two
estimators cannot drift apart on the definition of a rating point.

```python
    # Glicko-2 works on a transformed scale; convert at the boundary only.
    @property
    def mu(self) -> float:
        return (self.rating - DEFAULT_RATING) / SCALE

    @property
    def phi(self) -> float:
        return self.rd / SCALE
```

So a rating of 1500 is `mu = 0`, and RD 200 is `phi = 1.1513`. "Convert at the boundary only"
matters for reading the file: past `player.mu`, everything is internal-scale until the two
`* SCALE + DEFAULT_RATING` expressions at the return.

The two per-opponent helpers:

```python
def _g(phi: float) -> float:
    """Weight an opponent's contribution by how well-known their rating is."""
    return 1.0 / math.sqrt(1.0 + 3.0 * phi * phi / (math.pi * math.pi))


def _expected(mu: float, mu_j: float, g_j: float) -> float:
    """Probability that the competitor at `mu` beats the one at `mu_j`, whose weight is `g_j`."""
    return 1.0 / (1.0 + math.exp(-g_j * (mu - mu_j)))
```

`_expected` is the Elo logistic with two changes: natural-log units, and the rating gap is
multiplied by `g_j` before entering the exponent. Multiplying the gap by a number below 1
**flattens the curve** — an uncertain opponent makes every prediction closer to a coin flip. For a
200-point gap: against RD 45 the expectation is 0.7576, essentially Elo's 76%; against RD 350 it
falls to 0.6836.

### Step 3: v, how much information the games carried

```python
    for opp, score in opponents:
        g = _g(opp.phi)
        e = _expected(mu, opp.mu, g)
        v_inv += g * g * e * (1.0 - e)
        delta_sum += g * (score - e)

    v = 1.0 / v_inv
```

`v` is the variance of the rating estimate implied by these games. It is the reciprocal of a sum,
so it runs opposite to intuition: **small v means informative games.** Each game contributes
`g² · E · (1−E)`, which is largest when `E` is near 0.5 and collapses toward zero as `E` approaches
0 or 1 — a coin-flip game is informative, a foregone conclusion is not.

On the paper's example:

| opponent | g | E | contributes to 1/v | to delta_sum |
|---|---|---|---|---|
| 1400, RD 30 | 0.9955 | 0.6395 | 0.2285 | +0.3589 (won) |
| 1550, RD 100 | 0.9531 | 0.4318 | 0.2229 | −0.4116 (lost) |
| 1700, RD 300 | 0.7242 | 0.3028 | 0.1107 | −0.2193 (lost) |

Total `1/v = 0.5621`, so `v = 1.7790`. The 1700-rated opponent contributed less than half the
information of the 1550-rated one, for two reasons at once: the game was more lopsided (E = 0.30)
*and* that opponent's own rating was poorly known (g = 0.72).

Both facts bear directly on this project. A player meeting a puzzle for the first time meets a
competitor at RD 350, so `g = 0.669` and the game is discounted. And a gated tree serves puzzles
close to the player's level, which pushes `E` toward 0.5 — that part is *good* for information per
attempt. What gating costs is something else entirely, and it is the subject of section 7.

### Step 4: delta, the move the games alone suggest

```python
    delta = v * delta_sum
```

`delta_sum` is the `g`-weighted "actual minus expected" residual — the direction to move. Scaling
it by `v` gives `delta`: the move you would make if you fully trusted these games and had no prior
estimate to defend. On the example, `delta_sum = −0.2720` and `delta = −0.4839`. It is not the move
actually applied — step 7 shrinks it — but step 5 needs it, because how far the games *want* to
pull you is precisely the evidence about whether this competitor is erratic.

### Step 5: the new volatility

This is the fiddly part. Steps 3, 4, 6, 7 and 8 are formulas you transcribe. Step 5 is a
one-dimensional root find, because the volatility update has no closed form.

Glickman puts a prior on `ln(sigma²)` centred on its old value with spread `tau`, writes down the
function whose zero is the posterior mode, and solves `f(x) = 0` numerically. A large `delta²`
relative to what existing uncertainty (`phi² + v`) can explain pushes the root above the old
value: the results swung further than current volatility accounts for, so volatility rises. A
quiet period pushes it down.

```python
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
```

**Regula falsi** ("false position") is the method: given two points whose function values have
opposite signs, the root lies between them; draw a line through them, take its zero crossing as
the next guess, keep whichever pair still straddles the root.

The two branches are the two signs of `delta² − (phi² + v)`:

- **The bracketing branch.** When `delta_sq > phi_sq + v`, the point `ln(delta² − phi² − v)` sits
  on the far side of the root from `a`: there the first term of `f` is exactly zero, while at `a`
  the second term is exactly zero, and the two have opposite signs. The bracket is free.
- **The else-branch walks downward in steps of tau.** When `delta²` does not exceed `phi² + v`,
  the games swung no further than existing uncertainty already explains, so the answer lies *below*
  the old volatility. There is no closed form for where, so the code steps down from `a` by `tau`
  at a time until `f` stops being negative. `tau` is the natural step because it is the prior's own
  spread. The `k > 100` guard turns a pathological input into a loud error rather than a hang.

**The `fA /= 2.0` is what makes this "Illinois" rather than plain false position, and it is not
cosmetic.** `B` is always replaced by the newest guess; `A` is replaced only when the sign change
falls between the old `B` and `C`. If the root keeps landing on the same side, `A` never moves, the
secant keeps being drawn from the same stale point, and convergence stalls one-sidedly. Halving the
retained endpoint's function value tilts the next secant back and restores fast convergence.

Measured on the paper's example, with and without that one line:

| variant | iterations | returned sigma' |
|---|---|---|
| as written (Illinois) | 2 | 0.059996 |
| with the halving removed | 100 (hits the cap) | 0.060000 |

Without it, `|B − A|` stalls around 1.34e-4 and never reaches `EPSILON = 1e-6`, the loop exhausts
its cap, and since the function returns `exp(A/2)` with `A` never updated, it hands back the
**input volatility unchanged**. No exception, no warning: a silent "volatility did not move". That
is exactly the class of bug the docstring warns about, and it is why this function follows the
paper step by step instead of being simplified.

### Steps 6–7: inflate, then shrink

```python
    phi_star = math.sqrt(phi ** 2 + sigma_prime ** 2)
    phi_prime = 1.0 / math.sqrt(1.0 / (phi_star * phi_star) + 1.0 / v)
    mu_prime = mu + phi_prime * phi_prime * delta_sum
```

Step 6 inflates the pre-period deviation to account for drift since the last period: two
independent uncertainties add *in quadrature*. On the example `phi = 1.15129` becomes
`phi_star = 1.15285`, a small inflation because volatility 0.06 is small next to a deviation of
1.15.

Step 7 then folds in the games, and uncertainty shrinks. **Precisions** — reciprocal variances —
add: `1/phi_star²` is what you knew coming in, `1/v` is what the games told you, and the new
deviation is the reciprocal of the total. On the example, `phi_prime = 0.87220`, which is RD 151.52
back on the rating scale, down from 200 because three games were played.

The rating line deserves care, because it is where transcriptions go wrong. It multiplies
`phi_prime²` by **`delta_sum`, the raw residual from step 3 — not by `delta`**. Since
`delta = v · delta_sum`, the line is equivalent to:

```
mu' = mu + (phi_prime² / v) * delta
```

which is where the intuition lives. `delta` is the move the games alone suggest; `phi_prime² / v`
is the share of your total precision that came from those games, a number between 0 and 1. So the
applied move is a fraction of the full move, and the fraction is exactly how much of what you now
know is owed to this batch. On the example the share is 0.4276: the games said −0.4839, and the
update applies −0.2069.

Read the other way: it is the new, *smaller* deviation that scales the step. A competitor already
pinned down barely moves; a fresh puzzle at RD 350 moves a long way on its first attempts. Same
formula. That is the behaviour you want from an estimator serving 10,160 puzzles with wildly
different attempt counts.

Substituting `delta` for `delta_sum` here gives 1436.05 instead of 1464.05 — a 28-point error from
one factor.

### Step 8: convert back, through one exit

```python
    return _clamped(mu_prime * SCALE + DEFAULT_RATING, phi_prime * SCALE,
                    sigma_prime, player.games + len(opponents), player.rating)
```

`_clamped` is not Glickman; it is the production guard set from section 4, routed through one
helper for a stated reason:

```python
def _clamped(rating: float, rd: float, vol: float, games: int, prev_rating: float) -> Rating:
    """The single exit from `update`, so the Lichess clamps apply to every path identically.

    They used to be open-coded per branch, which meant each of update()'s exits enforced a
    different subset of them.
    """
```

`update()` has three exits — the ordinary path, the empty-period path, and the saturation path —
and all three return through it.

### The empty rating period

```python
    if not opponents:
        # No games: only uncertainty grows.
        phi_star = math.sqrt(phi ** 2 + player.vol ** 2)
        return _clamped(player.rating, phi_star * SCALE, player.vol,
                        player.games, player.rating)
```

This is step 6 alone. The rating is held exactly; the deviation grows. A competitor at
1600 / RD 100 / 0.06 comes out at 1600 / RD 100.5417, which `tests/test_glicko2.py` pins. The
principle: no games is not evidence, so the estimate must not move — but time passed, and the model
says true strength drifts at a rate governed by volatility, so confidence decays while the point
estimate stands. A system that instead pulled idle ratings toward 1500 would be inventing results
that were never played.

**There is a real tension here, and it is worth naming rather than papering over.** A *player's*
strength genuinely drifts between periods; a *puzzle's* difficulty does not — the position on the
board is the same position it was last year. Inflating a puzzle's uncertainty purely because the
calendar advanced models player-style drift where none exists, and running calendar rating periods
over the whole catalogue would march the rarely-attempted tail toward `MAX_DEVIATION = 500` on no
information at all. The honest resolution: what genuinely goes stale is the *audience* — who is
attempting the puzzle, and with what prior exposure — not the position. That justifies some
inflation, but far less than a per-calendar-period application would produce. This repo never hits
the branch, because `replay` calls `play()` per attempt, so every update has exactly one opponent.
Anyone taking this to production should decide deliberately whether puzzles get rating periods at
all, or only ever update when attempted.

### The saturation path: a 6,447-point gap

```python
    if v_inv <= 0.0:
        # Every opponent's E saturated to 0 or 1 in float64, so v -> infinity. Steps 6-7 still
        # have a limit there — phi' -> phi_star and mu' = mu + phi_star^2 * delta_sum — and
        # delta_sum is *not* zero, so taking the limit keeps the game instead of discarding it.
        # (Reachable at roughly 6,400 points of rating gap, where exp() saturates.)
```

`_expected` computes `1 / (1 + exp(-g·(mu − mu_j)))`. Once that exponent's argument exceeds about
36.7, `exp(...)` is smaller than half a float64 step at 1.0 and the whole expression rounds to
**exactly** 1.0. Against an opponent at RD 45, that happens at a gap of 6,446.6 rating points.
`E · (1−E)` is then exactly 0.0, so `v_inv` is 0.0 and `v = 1/v_inv` would divide by zero.

But the step-4 sum does *not* vanish: `g · (score − E)` with score 0 and E 1.0 is −0.98996, a
full-strength "you lost to something 6,450 points below you", which is a very real result. The
information is there; only the variance underflowed. So the code takes the limit rather than the
division: as `v → ∞`, `phi_prime → phi_star` and `mu' = mu + phi_star² · delta_sum`.

The tempting alternative — `return player` — is wrong, and worse, quiet. It would silently discard
a game whose residual was maximal, and a rating stuck at an absurd value could never escape,
because every subsequent attempt against a normal opponent would also saturate and also be thrown
away. **This was a bug found and fixed during review.** `tests/test_glicko2.py` sends a
7950 / 350 / 0.09 competitor to a loss against 1500 / 45 and pins the result at 7250.52 / RD
350.35, with the game counted.

### play(): both sides update against the other's pre-update state

```python
    p_before, z_before = player, puzzle
    p_score = 1.0 if solved else 0.0

    new_player = update(p_before, [(z_before, p_score)], tau)
    new_puzzle = update(z_before, [(p_before, 1.0 - p_score)], tau)
```

Both calls read `p_before` and `z_before`; nothing the first computes is visible to the second.
That simultaneity is the point. If you updated the player first and fed the *updated* player into
the puzzle's update, the puzzle would be scored against a rating that had already absorbed this
same attempt — the evidence counted twice, in one direction. Over a long log, whichever side
updates second is permanently chasing the other.

The test pins the symmetric case: with both at 1500 / 200 / 0.06, the solver's gain and the
puzzle's loss sum to zero within 1e-9. That exact cancellation is a property of symmetry, not a
general law, and **the way it fails is the useful part.** Each side's step is scaled by its own
`phi_prime` and by `g` of the *other* side's deviation. So a well-measured player at RD 45 meeting
a fresh puzzle at RD 350 moves the puzzle a long way and barely moves themselves: `g(350) = 0.669`
damps what the player learns while the puzzle's large `phi_prime` amplifies what the puzzle learns.
Information flows from the better-known side to the less-known side, automatically, in proportion
to how much better known it is. That is what "mutually calibrating" means: neither is an anchor,
and whichever is currently more certain does most of the teaching.

### What the validation establishes

| | rating | RD | volatility |
|---|---|---|---|
| this implementation | 1464.0507 | 151.5165 | 0.059996 |
| the paper prints | 1464.06 | 151.52 | 0.05999 |

The residual hundredth is the paper's own rounding — Glickman rounds intermediate quantities as he
prints them, so recomputing his chain from rounded values cannot reproduce an unrounded one
exactly.

What a two-decimal match establishes: **every one of steps 3 through 8, the volatility root finder
included, agrees with the reference to roughly one part in 100,000.** That is strong because the
test is well-conditioned — the errors that actually occur do not hide in the second decimal.
Substituting `delta` for `delta_sum` moves the answer 28 points. Dropping `g` from the
expected-score formula gives 1470.02 / RD 152.42. Removing one line from the Illinois solver stops
it converging at all. Every one of those passes a smoke test and fails this one.

What it does *not* establish: this is one period, three games, one set of starting values. It
validates the arithmetic, not the modelling — not that a puzzle is a sensible competitor, not that
one latent trait describes Go skill, not that the Lichess constants are right. The value of pinning
the arithmetic first is that everything downstream becomes a statement about the *data*, with the
estimator ruled out as a source of the effect.

---

## 4. From the paper to a production system

Glickman's paper specifies an algorithm and stops. It does not tell you which observations are
allowed into the log, what to do when one is absurd, or what to do when the way a puzzle was
*presented* is part of why it was solved. Those are the questions between the paper and something
you could point at a real database.

### The Lichess clamps

```python
TAU = 0.75                # system constant: how fast volatility moves. Glickman suggests 0.3–1.2
MIN_DEVIATION = 45.0      # a rating never claims to be more certain than this
MAX_DEVIATION = 500.0
MAX_VOLATILITY = 0.1
MAX_RATING_DELTA = 700.0  # a single game can never move a rating further than this
```

**`MIN_DEVIATION = 45` — a floor on uncertainty.** RD shrinks as evidence accumulates and nothing
in the paper stops it reaching zero. Puzzles are the long-lived side of this system: a player plays
for a season, a puzzle collects attempts forever. It takes about 4,810 balanced games to press RD
from 350 down to 45, and a popular puzzle will see many times that. Without a floor, RD keeps
falling — and RD is what buys a rating the right to move. One loss to an equal opponent moves a
rating 6.35 points at RD 45, 1.83 at RD 20, and 0.77 at RD 5. That last rating is frozen: it cannot
respond to anything real, because it has convinced itself it already knows the answer. The floor
keeps every rating permanently corrigible.

**`MAX_DEVIATION = 500` — a ceiling on uncertainty.** The reverse problem. In an empty period RD
grows, applied again every period, so a dormant competitor inflates without bound — and RD feeds
the next update quadratically. Take a 6,000-point upset and lift the delta cap: at RD 350 the
uncapped move is 699.5 points, at RD 500 it is 1,426, at RD 800 it is 3,649. The ceiling stops a
dormant rating from becoming a loaded spring. Since `DEFAULT_RD` is 350, it allows 150 points of
drift headroom and no more.

**`MAX_VOLATILITY = 0.1` — a leash on the solver.** Volatility feeds the next period's `phi_star`,
a large `phi_star` inflates RD, a large RD enlarges the next move, and a large move can produce
another surprise. It is a positive feedback loop and it does run away. `DEFAULT_VOL` is 0.09, so
0.1 permits about 11% headroom above the starting value — a leash, not a safety net. The cap is
applied twice on purpose: once on the solver's own output, so the inflated value never reaches
`phi_star`, and again in `_clamped`.

**`MAX_RATING_DELTA = 700` — a cap on one result.** The last-resort backstop against one freak
result — a beginner solving a puzzle the system believes is worth 7,500, by luck or because the
answer was shared. Recovery from that is slow, because the wrong rating is what selects subsequent
opponents, so every following pairing is itself mismatched. The calibration is interesting: at
`DEFAULT_RD` 350 the largest move the arithmetic can actually produce is 699.5 points — just
*under* the cap, which therefore does not bind on a fresh rating at all. It only bites once RD has
inflated past 350, which is why it and `MAX_DEVIATION` are two halves of one guard. (Against a
hypothetically perfectly-known opponent, `g = 1`, the uncapped move would be 706.6 and the cap
would bind by 6 points.)

**`TAU = 0.75` — the one constant Glickman leaves to you.** He suggests 0.3–1.2 and declines to
pick; Lichess took the slow-moving end of the middle. His worked example uses 0.5, and the repo's
test passes that explicitly. That is not a contradiction: `tau` is an *input* to the algorithm, not
part of it, and both `update()` and `play()` take it as a parameter defaulting to the module
constant. The test's job is to check steps 3–8 against printed numbers, and the only way to do that
is to feed the paper's own inputs, `tau` included. Had it used 0.75 it would have been testing the
constant instead of the arithmetic, with nothing to compare against.

**How much any of this matters to the experiment: none of it.** The sweep never runs an empty
rating period, so RD never grows past 350 and the 500 ceiling is inert. At RD 350 the delta cap
does not bind. And the largest volume in the sweep, 160 attempts per puzzle, is a factor of 30
short of the ~4,810 games needed to reach the RD floor. Every number in sections 5–7 would be
identical with all four clamps removed. They are here because a production deployment needs them,
not because the experiment does.

### What counts as an observation: first attempts only

The rule is one observation per player per puzzle — the first — and never a retry.

A first attempt is a draw from "can this player, cold, read out this position", which is exactly
the quantity being estimated. A second attempt after a failure is a draw from something else: you
have seen the position, you know a move that does not work, and if the site showed the solution you
are being asked whether you can remember it. That measures recall, and recall of a position you
just studied is much easier than the position was.

Feeding retries in undamped drags every puzzle's rating downward, and two things make that worse
than a simple bias:

- **The bias is not uniform, so it does not cancel.** Harder puzzles generate more failures, hence
  more retries, hence more spuriously easy observations. The downward pressure is proportional to
  difficulty. A uniform shift would be harmless — RMSE(off) removes a mean offset by construction —
  but a difficulty-proportional shift is *scale compression*, which section 7 shows is already the
  dominant failure mode on gated data. Retries would add to the one error the estimator is worst at.
- **RD falls as though the retries were independent.** Glicko has no notion of correlated
  observations; every game in the log shrinks uncertainty. Ten retries by one player on one puzzle
  are one observation wearing ten hats, and the rating comes out over-confident about a number that
  is also wrong.

### The lives mechanic, and the outcome definition it forces

Go Magic gives one or two lives per puzzle. This is deliberate design, not leniency: the point is
to make you read the position out before touching the board. You may retry after failing, but a
retried solve earns no coins and no XP.

**The blocking data dependency is much smaller than it looks.** A first-attempt-only rule needs to
know, for every (user, puzzle) pair, whether this is the first try — which sounds like a schema
change and a backfill. But a lives counter cannot work without exactly that field: to show a player
their second life, the system must already know they used the first. Whatever table drives the
lives UI is the table a first-attempt-only extraction reads.

**And the justification becomes principled rather than borrowed.** "First attempts only" could be
dismissed as a Lichess convention adopted because Lichess adopted it. Here it falls out of Go
Magic's own design: a post-failure attempt is explicitly unrewarded — the product itself declines
to count it — *and* it is taken after seeing the position. Both reasons point the same way.

**But the number of lives forces a modelling decision that is easy to make by accident.** "Solved
on the first life" and "solved within the allowed lives" are two different binary outcomes, and
Glicko-2 fitted on them produces two different difficulty scales for the same catalogue — not
noisier versions of one scale, but different scales with different origins and spacings, which
cannot be compared or pooled.

| | first life only | within allowed lives |
|---|---|---|
| what it measures | can you read this out cold | can you get there with the site's help |
| fit to the estimator | one trial, one binary outcome, matching the model directly | a mixture of two trials reported as one; the model is told a single draw happened |
| fit to the product | stricter than what the UI calls success | exactly what the player experiences as success |
| stability | a property of the puzzle | a property of the puzzle **and** of a product setting |

The stability row decides it. Because lives are "one or two", the allowed count is not constant
across the catalogue, so "solved within allowed lives" is not even a consistent outcome definition:
a two-life puzzle rates as easier than a one-life puzzle of identical true difficulty purely
because it granted an extra trial, and nothing in the rating records which happened. Change a
puzzle from two lives to one later and every derived rating moves without anything about the puzzle
changing. First-life-only has neither problem.

The counter-argument is real, though: within-lives is what the product *means* by "solved", so a
scale built on it will match players' intuitions and will drive a recommender optimising the
experience the site actually ships. If you want both, fit both and store both, labelled. What you
must not do is let the choice happen implicitly because that was the easiest column to join on.

**One side effect in this project's favour.** Because lives punish careless clicking, players are
pushed to read before touching the board. An app that lets you click freely collects many outcomes
that are mostly guessing, and guessing makes easy and hard puzzles look more alike — scale
compression again. Go Magic's outcomes should carry less of that noise than the typical case: a
genuine, if unquantified, advantage.

### Hint damping

A rating implicitly assumes every observation was collected the same way. `play()` has a `weight`
parameter for when it was not, and `_lerp` applies only `w` of the computed update.

The argument that a skill tree is inherently a hinting context is short and hard to escape. To
reach a puzzle you navigated to a named node — "Nakade Shapes" — then a level, then a quiz. By the
time the position appears you have been told what kind of problem it is, and in Go that is a large
fraction of the work: knowing you are looking for a nakade tells you to find the vital point of an
eyespace, which rules out most of the board. The observation is therefore not "can this player
solve this position" but "can this player solve this position *given the theme*" — a different item
with a different difficulty. The tree cannot be made non-hinting without dismantling the tree,
since the categorisation is the pedagogical point.

A blind diagnostic test is the other case: the position arrives with no label, so the outcome is
about the position.

Pool them without tracking which is which, and each puzzle's rating becomes a traffic-weighted
average of its hinted and blind difficulties, with the weight differing per puzzle by where its
traffic came from. That difference is indistinguishable after the fact from a difference in
difficulty — the rating is three numbers and none of them is provenance. It is unrecoverable in
the way a missing column always is.

Be precise about what `weight` does and does not fix. It reduces how much a hinted attempt
*influences* the rating; it does not convert a hinted observation into a blind one, so it shrinks
the bias in proportion to the weight rather than removing it. The durable fix is a context flag
stored next to every attempt, which lets a later joint fit carry an explicit per-context difficulty
offset — the same machinery as `batch_fit.py` with one more parameter. Damping is the online-path
approximation of that; the flag is the thing you cannot add retroactively.

Two honest notes on the code. The sweep does not use damping at all, so the gated regime in section
7 is modelled as gated *but not hinted*: it pays the restriction-of-range penalty and gets the full
information content of every observation for free. Real tree traffic pays both, so the gated numbers
are slightly optimistic — the direction of that error is known even though its size is not. And
`weight=0.0` is now a true no-op on rating, RD and volatility while still incrementing `games`;
volatility used to pass through undamped, so "ignore this observation entirely" quietly did not.
That was a bug found during review, and the test pins all four behaviours now.

---

## 5. The experiment: how you test an estimator with no ground truth

### Plant a world

The trick that makes any of this measurable is planting the truth yourself:

```python
def make_world(n_puzzles: int, n_players: int, rng: random.Random) -> Sim:
    """Plant a population. Difficulties and skills both span the kyu range."""
    puzzles = [rng.gauss(DEFAULT_RATING, TRUE_SD) for _ in range(n_puzzles)]
    players = [rng.gauss(DEFAULT_RATING, TRUE_SD) for _ in range(n_players)]
    return Sim(puzzles, players)
```

Each puzzle gets a *true difficulty*, each player a *true skill*, drawn from a Gaussian centred on
1500 with standard deviation `TRUE_SD = RANK_SPREAD / 3 = 466.67` rating points. That choice is not
arbitrary: at ~100 points per rank the kyu range from 20k to 1d spans 1400 points, so an sd of a
third of that puts the kyu range at exactly ±1.5 sd around the centre — the bulk of the population
inside the range a real Go site serves, with thin tails past both ends.

Because you planted the truth, recovery error is not an estimate or a proxy. After fitting you have
300 fitted difficulties and the 300 numbers they were supposed to recover, and you can subtract
them. That is the entire trick, and the only reason "how much data is enough" has a numeric answer.

### Generate outcomes

```python
def solves(skill: float, difficulty: float, rng: random.Random) -> bool:
    """Logistic outcome on the true latent values. 400-point scale, as in Elo."""
    p = 1.0 / (1.0 + 10 ** ((difficulty - skill) / 400.0))
    return rng.random() < p
```

If your skill equals the difficulty you solve half the time. A puzzle 100 points above you — one
rank harder — you solve 36% of the time; 400 points above, 9%.

The important property is not the shape but that **it is the same functional form Glicko-2
assumes**, and the same form the joint fit in section 7 uses. So the simulation contains **no model
misspecification** — no mismatch between the process generating the data and the model fitted to it.

That is deliberate, and it is the generous choice. Reality has plenty of misspecification: Go skill
is not one-dimensional, players learn between attempts, some outcomes are lucky guesses, difficulty
is not a single scalar. Every one of those makes recovery harder.

Being generous is right because of what the experiment is *for*. The interesting results here are
failures — "at 10 attempts per puzzle under gating the error is 404 rating points". If the simulated
world were harsher than reality, a critic could dismiss that as an artefact of a badly chosen
simulation. Because the simulated world is the model's own world, the number is a **floor**: real
data can only push it up. Conclusions of the form "you need at least this much" survive;
conclusions of the form "this much is plenty" would not, and none are made.

### Build the log, then replay it

`make_log` and `replay` are two functions rather than one because two different estimators must be
scored on one dataset. `make_log` returns a plain list of `(player, puzzle, outcome)` tuples, and
its docstring states the contract:

> This is the single source of the attempt log. Both estimators — online Glicko-2 in `replay`
> below, and the joint fit in `batch_fit.py` — are scored on the *same* list returned from here,
> which is the only way the online-vs-batch comparison is a comparison of estimators rather
> than of two different random draws.

**This factoring was the fix for a real defect found in review.** Previously `batch_fit.py` carried
its own copy of the generator, and that copy interleaved outcome draws with pairing draws while
`recovery.py` did them in two passes. Two copies drawing from the same seed in a different order
diverge immediately: the two logs overlapped on **0.1%** of their (player, puzzle) pairs, while the
file printed *"Both see the identical attempt log."* Every online-versus-batch difference in that
version was partly a comparison of two unrelated random draws. Now there is one list, so the
`online` rows in section 7's batch table are the same runs as its sweep table, digit for digit.

Two details inside the generator matter to the result:

```python
        pairs.extend((pi, zi) for pi in rng.sample(pool, min(attempts_per_puzzle, len(pool))))

    # Order matters to an online estimator, and a real log is chronological, not grouped.
    rng.shuffle(pairs)
    return [(pi, zi, 1.0 if solves(sim.players[pi], sim.puzzles[zi], rng) else 0.0)
            for pi, zi in pairs]
```

**The shuffle.** An online estimator's state at attempt *k* depends on attempts 1…*k*−1, so log
order changes the answer. Pairs are built puzzle by puzzle, which would hand the estimator all 160
attempts on puzzle 1, then all 160 on puzzle 2 — an ordering no real log has. Shuffling produces
the chronological interleaving a real log has.

**The sample.** `sample` draws without replacement, so no (player, puzzle) pair appears twice. That
is the first-attempts-only rule from section 4, enforced in the generator rather than filtered
afterwards, so a repeat attempt cannot leak in.

### The gating model

```python
        ungated = rng.random() < linking
        if banded and not ungated:
            pool = [i for i, s in enumerate(sim.players) if abs(s - zdiff) <= band]
            if len(pool) < attempts_per_puzzle:
                pool = sorted(everyone, key=lambda i: abs(sim.players[i] - zdiff))[
                    :attempts_per_puzzle]
        else:
            pool = everyone
```

`banded=False` is the **ungated** regime — any player can meet any puzzle, which is what a
diagnostic test looks like, and deliberately the easy case.

`banded=True` models a skill tree. Progression means a player only reaches puzzles near their own
level, so with `band = 300.0` (about three ranks either side) a player planted at 1500 only ever
meets puzzles between 1200 and 1800. The resulting attempt matrix — players down the side, puzzles
across the top — is *banded*: entries cluster along the diagonal instead of filling the grid. No
single attempt directly connects the two ends of the scale.

**The fallback.** A puzzle planted far out in the tail may have fewer than `attempts_per_puzzle`
players within 300 points, because few of the 3,000 drawn players are that strong. The fallback
takes the *nearest* N instead. Without it, tail puzzles would silently collect fewer attempts, and
"160 attempts per puzzle" would mean 160 for most and 12 for the tail — the RMSE would blend a
gating effect with a sample-size effect and the two could not be separated. With it, every puzzle
gets exactly the requested number in every regime, and the only thing differing between regimes is
**who** attempted each puzzle. That is the isolation the experiment needs. It is also, again,
generous to the gated regime.

**Linking.** `linking` is the fraction of *puzzles* served ungated even in the gated regime — what
psychometrics calls **common items** or **linking items**. Because every puzzle receives the same
number of attempts, the fraction of ungated puzzles is also the fraction of ungated traffic, so the
knob reads directly as a traffic budget.

Note that the `ungated` draw happens unconditionally, before the branch, so every regime consumes
the same position in the random stream and all regimes at a given sweep point are compared on the
same planted world with the same pairing draws. The payoff is a free consistency check: at
`linking=1.0` every puzzle is served ungated, so the gated regime must become *identical* to the
ungated one — and it does, landing on the same digits (section 7).

### Scoring

`score_values` computes both error metrics at once, plus `slope`, `within_100` (share inside ±100
points, i.e. one rank, under the offset-only alignment) and `rho` (Spearman rank correlation — the
correlation of *ranks*, so 1.0 means the ordering is exactly right however wrong the spacing).
Section 6 owns the argument for why there are two metrics; operationally, `rmse_offset` is primary.

Two bookkeeping details keep it honest. `score()` filters on `f.games > 0`, because a puzzle nobody
attempted still holds its default 1500 and scoring that would credit the estimator for the planted
mean. And `batch_fit.py` scores both estimators on the same subset — the puzzles the shared log
actually touches — so neither is graded on a different set than the other.

### Reproducibility

Everything is seeded from 20260816, and both files derive sub-streams by the same arithmetic —
worlds from `seed + r*977`, logs from `seed + r*7919 + n` — which is why the `online` rows in the
batch comparison are literally the same runs as the sweep.

One planted world per repetition, reused at every sweep point:

```python
    # One planted world per rep, reused at every sweep point. Drawing a fresh world per point
    # would make the RMSE-vs-attempts curve partly a plot of world-to-world variation.
```

This matters more than it looks. Two draws of 300 puzzles differ noticeably in how their
difficulties happen to be spaced. With a fresh world per point, the error-versus-attempts curve
would mix "more data helps" with "this world happened to be easier", and the *shape* of that curve
is the entire finding.

The commands, all at seed 20260816 with puzzles and reps as shown (note that `recovery.py`'s own
defaults are 400 puzzles and 3 reps, which the published tables override):

```sh
./tests/test_glicko2.py                                            # validate the estimator
./src/parse_tree.py --html data/skilltree-2026-08-16.html           # the section-1 inventory, offline
./src/recovery.py --puzzles 300 --reps 2                            # the sweep; writes out/recovery.png
./src/batch_fit.py --puzzles 300 --reps 2                           # online vs joint fit on one log
./src/recovery.py --puzzles 300 --reps 2 --linking 0.25 0.5 1.0     # the dose-response
```

`--band`, `--linking`, `--l2` and `--iters` are flags rather than buried constants, so the
sensitivity of any conclusion to any of them can be checked without editing source.

### What the design does not test

Stating these plainly, because several of them would change the numbers:

- **No confidence intervals anywhere.** Every table is a mean over `--reps` worlds with no standard
  error computed, so differences of a few RMSE points between adjacent cells are not resolvable.
  The gaps the conclusions rest on are 100 points and more.
- **Gating is modelled on planted truth, not on tree position.** The band selects on
  `|true skill − true difficulty|`. Real gating is on tree progression against *hand-assigned*
  difficulty, a noisy proxy for both. That makes the simulated band tighter and cleaner than the
  product's; the direction of the resulting error is not obvious.
- **Every puzzle receives exactly N attempts.** Real traffic is a power law over a tree with
  prerequisite depth. The uniform-N design is what makes the sweep readable, and it is the reason
  section 7 can warn about per-puzzle coverage without having measured the uneven case.
- **Player-side recovery is never scored.** Both estimators fit 3,000 player skills; every table
  scores only puzzles. Player recovery is the harder case — at 160 attempts per puzzle the log
  averages about 16 attempts per player — and it is out of scope here, not solved.
- **Planted difficulty is static,** so nothing ever exercises the drift that volatility exists to
  track. Volatility is implemented and validated, and idle in this experiment.
- **300 puzzles, not 10,160.** The sweep's x-axis is attempts *per puzzle*, which is the quantity
  that governs per-puzzle precision, so the per-puzzle numbers should transfer. What does not
  automatically transfer is anything depending on catalogue size — in particular the linkage
  structure of a much larger banded matrix.

---

## 6. What "measured" means, and the two ways to be wrong

The estimator hands back one number per puzzle. Before asking "how close is that to the truth?"
you have to answer a prior question: close in *what sense*? The model has two loose degrees of
freedom, they are loose in different ways, and no single error number sees both. That sounds like a
technicality. It is not — getting it wrong nearly produced a false conclusion in this repo, and the
last part of this section is that story.

### The origin is free

Look at what enters the outcome model: `difficulty - skill`, and nothing else. Glicko-2 has the
same property; it works entirely on `mu - mu_j`.

So take any world and add 300 points to every player's skill *and* every puzzle's difficulty. Every
gap is unchanged, so every solve probability is unchanged, so every possible attempt log has exactly
the same probability of occurring. Illustratively:

| skill | difficulty | gap | P(solve) | | skill +300 | difficulty +300 | gap | P(solve) |
|---|---|---|---|---|---|---|---|---|
| 1500 | 1500 | 0 | 0.500 | | 1800 | 1800 | 0 | 0.500 |
| 1500 | 1300 | −200 | 0.760 | | 1800 | 1600 | −200 | 0.760 |
| 1500 | 1700 | +200 | 0.240 | | 1800 | 2000 | +200 | 0.240 |

The two worlds are observationally identical. No amount of data separates them, because no
observation differs between them. The word for this is **identifiability**: a parameter is
identifiable if different values of it imply different distributions over the data. The absolute
level of difficulty is *not* identifiable here. Only differences are.

So a raw RMSE against planted difficulties is not a measure of estimator quality — it is partly a
measure of where the fit happened to park an arbitrary origin. Aligning before scoring is not a
fudge that flatters the numbers; it is the only way to compute a number about the estimator rather
than about a convention.

`batch_fit.py` handles this explicitly, and the comment is worth reading closely:

```python
        # z = theta - beta has exactly one degeneracy, a common shift, so exactly one constraint
        # is free. Pinning both means would impose two and destroy the identifiable difference
        # between mean skill and mean difficulty; the Rasch convention is to pin the items.
        beta -= beta.mean()
```

One degeneracy, one constraint. Mean puzzle difficulty is pinned to zero, fixing the origin by
decree, and mean *player* skill is then free to land where the data says — because "the average
player is 340 points above the average puzzle" *is* identifiable, and pinning both means would
throw that away. (Pinning both was a bug found during review.)

The reassuring part: relative difficulty is exactly what a difficulty label needs. "This puzzle is
200 points harder than that one" is a statement about the world. "This puzzle is 1700" is a
statement about the world *plus* a chosen zero — which is fine, since 1500 is as arbitrary a zero
as sea level, and both are useful once fixed.

### The second freedom is the scale, and it is subtler

The origin is unidentifiable in principle — no estimator, no volume of data, ever recovers it. The
scale is different. The logistic link with its 400-point denominator *does* pin the units in
principle: a 200-point gap means a 24% solve rate, and that is checkable against data. The scale is
identifiable. It is just badly estimated when the data is weakly linked, and a MAP prior shrinks it
further.

Here is the failure, with invented numbers chosen to be clean. Five puzzles; the fit gets every one
in the right order but halves every gap and adds a 40-point offset:

| puzzle | true | fitted |
|---|---|---|
| A | 1100 | 1340 |
| B | 1300 | 1440 |
| C | 1500 | 1540 |
| D | 1700 | 1640 |
| E | 1900 | 1740 |

Rank correlation is a perfect 1.0 and every "is A harder than B" question is answered correctly.
Yet the fit says A and E differ by 400 points when they really differ by 800.

That is not hypothetical — it is what online Glicko-2 does under gating at high volume. At 160
attempts per puzzle, gated, the sweep reports **rho 0.95** alongside **slope 2.35**, with
**RMSE(off) 279**. In product terms this is a specific, diagnosable failure rather than general
noise:

- **Anything consuming ordering works.** "Show me the hardest life-and-death puzzles." "Is this
  harder than the one they just failed?" Rho 0.95 supports those.
- **Anything consuming the magnitude is wrong.** Suppose an adaptive selector aims for a 70% solve
  chance, which the logistic says is a puzzle about 150 points below the player. Apply that to a
  scale 2.35× too narrow and you actually reach about 350 real points below — a solve rate near
  88%. You designed a challenge and shipped a warm-up.
- **A displayed rank is wrong.** The planted population spans about 1400 points, roughly 14 ranks.
  Compressed by 2.35 it spans about 600 points, roughly 6 ranks. An 11-level table rendered from
  those numbers collapses toward the middle: almost everything reads as "intermediate".

One precision, since the slope gets quoted a lot: `slope = r · sd(truth) / sd(fitted)`, so the raw
spread ratio is `slope / r`, which exceeds the slope whenever `r < 1`. Reading "2.35× too narrow"
is therefore slightly conservative — in a single rep of that cell the raw ratio is about 2.5. The
error leans in the safe direction.

### The two metrics, operationally

Both live in `score_values`. **RMSE(off)** computes the mean of `fitted − truth`, subtracts that
one number from every fitted value, and takes the RMSE. It removes the origin — the one thing that
genuinely is not identifiable — and nothing else, so the fitted spacing survives and the compressed
toy fit above still scores badly. **RMSE(aff)** fits the best straight line taking fitted values to
true values, a slope *and* an intercept, applies it, and takes the RMSE of what is left.

Now the point that makes all of this load-bearing. RMSE(aff) is the residual RMSE of a
least-squares regression, and there is a closed form for that:

```
RMSE(aff) = sd(truth) * sqrt(1 - r^2)      r = Pearson correlation(fitted, truth)
```

Read the right-hand side. `sd(truth)` is a property of the planted world, fixed. `r` is a
correlation, invariant to any linear rescaling of the fitted values. So **RMSE(aff) contains no
information whatsoever about the fitted scale.** It is Pearson correlation wearing rating-point
units. Multiply every fitted difficulty by 7 and it does not move a digit. (This repo verifies the
identity numerically; it holds to 6e-14.)

Careful with names: the `rho` column everywhere is *Spearman* rank correlation, which measures
ordering only. The `r` above is *Pearson*, which measures linear agreement. Both get called
"correlation"; they are not the same number.

The two metrics are related exactly, and the relationship is the whole lesson:

```
RMSE(off)^2  =  RMSE(aff)^2  +  [ sd(fitted) * (slope - 1) ]^2
                 \________/       \___________________________/
                  ordering               compression
```

(Verified numerically to 1.5e-11 on a real sweep cell.) Check it against the five-puzzle toy:
`sd(truth)` is 282.84, `r` is 1.0, `slope` is 2.0, and the affine residual is exactly 0 because the
fit is perfectly linear. So all the error sits in the second term — and indeed the offset-only
errors are `[200, 100, 0, −100, −200]`, whose RMSE is 141.42. **The scale-free metric reports zero
error on a fit that halves every gap in the catalogue.**

Which brings us to the most instructive pair of cells in the experiment. Joint fit, 160 attempts:

| regime | RMSE(off) | RMSE(aff) | slope |
|---|---|---|---|
| ungated | 62.8 | 50.9 | 1.09 |
| gated | **102.8** | **38.7** | 1.28 |

The gated fit is *better* on RMSE(aff) and *worse* on RMSE(off). Both are true, and the identity
says why: gated pairing puts each puzzle against players near its own level, which is where each
attempt is most informative, so the *ordering* it learns is genuinely excellent. What gating
destroys is the linkage that pins the spacing — and the spacing error lands entirely in the
compression term.

So: pick the metric that removes scale, and gated data looks like the better dataset. Pick the
metric that keeps it, and gated data is 1.6× worse. Same log, same fit, same run.

### Why this nearly caused a wrong conclusion

An earlier draft of this repo's README diagnosed the gating failure correctly: gating does not
scramble the ordering, it compresses the scale — look at rho 0.95 with slope 2.35. That diagnosis
was right.

It then measured the joint refit as the fix and read the improvement off RMSE(aff): 139 down to 39
under gating, better than the 51 that ungated pairing scored, and concluded the gap "nearly
disappears".

That conclusion was an artefact of the instrument. The diagnosed failure was scale compression, and
RMSE(aff) removes scale by construction. **The metric could not have reported a scale failure if
one had been there, so its verdict of "cured" carried no evidence.** The number went down because
the affine map hands the compressed scale back for free.

The general shape of the trap is worth naming, because it is not specific to psychometrics: **if
you diagnose a failure mode and then evaluate the fix with an instrument that quotients out that
failure mode, you will always succeed.** The evaluation cannot fail. It is the measurement
equivalent of testing a bug fix with the assertion deleted, and it is more dangerous than an
outright mistake because the plumbing is all correct — the number is computed properly, it is just
answering a different question than the one you asked.

The resolution adopted here is procedural, not clever: report both metrics, always, with the slope
beside them. Both scripts print the reminder in their own headers, so the numbers cannot be read
without it.

The honest reading is still a strong result — 279 to 103 is a 63% cut, with slope 2.35 to 1.28 —
just not the result the flattering metric claimed.

### The oracle caveat

RMSE(aff)'s slope and intercept are least-squares-fitted **against the planted truth**. They are
chosen with the answer in hand. A production system does not have the answer — if it did, it would
not need to estimate difficulty. So RMSE(aff) is an *oracle* metric: it reports how good your fit
would be if someone handed you the correct rescaling, which nobody will.

The asymmetry with RMSE(off) is the thing to see. Both metrics touch the truth: the offset-only
alignment uses `mean(fitted − truth)`, which production also lacks. But the origin is a *free
convention* — declare that mean difficulty is 1500 and be done, exactly as `batch_fit.py` declares
`beta -= beta.mean()`. Nothing is lost, because the origin was never identifiable and never needed.
The scale is not a free convention. It is a real, checkable property of the world, and if your fit
understates it by 2.35×, declaring otherwise does not fix it.

Realising a rescale in production requires **anchor items**: puzzles whose difficulty is already
established on the scale you want, served alongside the new ones, so a fresh fit can be mapped onto
the established scale. That is the same machinery as linking items, used for a different purpose.
It is buildable — Go Magic's ungated diagnostic is a plausible home — but it has to be built. Until
it is, the scale-preserving number describes what you would actually ship.

---

## 7. What the experiment found

All numbers below are 300 planted puzzles, 3,000 planted players, seed 20260816, two repeats
averaged, from the three commands in section 5.

### How much data online Glicko-2 needs, ungated

The easy case first: any player can meet any puzzle. This is not what a skill tree does; it is what
a diagnostic test does. It is the ceiling.

| first attempts/puzzle | RMSE(off) | RMSE(aff) | slope | within ±100 | rho |
|---|---|---|---|---|---|
| 3 | 329.2 | 313.5 | 1.47 | 27% | 0.70 |
| 5 | 290.7 | 265.3 | 1.49 | 30% | 0.80 |
| 10 | 247.2 | 211.8 | 1.48 | 30% | 0.88 |
| 20 | 200.0 | 156.4 | 1.43 | 42% | 0.94 |
| 40 | 164.0 | 116.4 | 1.37 | 51% | 0.97 |
| 80 | 128.1 | 83.9 | 1.29 | 62% | 0.98 |
| 160 | 104.0 | 75.8 | 1.20 | 69% | 0.99 |

The curve is a straight line against log attempts: 329.2 down to 104.0 across 5.74 doublings, about
**39 RMSE points per doubling**. No knee, no cheap regime — every halving of error costs a doubling
of traffic.

It does not clear the one-rank line inside this sweep. At 160 attempts the typical error is 104
points, just above one rank; at 40 it is 164, about a rank and a half; at 10 it is 247, worse than
the granularity of the 11-level hand table it would replace.

**The `±100` column is the one to quote to a product person**, because a mean hides the
distribution. Even at 160 attempts per puzzle, 69% of puzzles land within one rank and **31% do
not**. At 40 attempts it is a coin flip. Averages get good before individual labels do.

Note the `slope` column too: even ungated, online Glicko-2 compresses — 1.48× too narrow at 10
attempts, still 1.20× at 160. Ordering arrives early (rho 0.88 at 10 attempts), spacing arrives
late.

Scaling that to the catalogue: 160 first attempts per puzzle across 10,160 puzzles is about **1.6
million first attempts**, and it must be 160 *per puzzle*, not 160 on average. In a tree, "160
first attempts on this puzzle" means 160 distinct players reached it — a modest number for a
popular site and a hopeless one for the deepest sdk nodes, which the fewest players reach.

### Restriction of range: why gating hurts

Now the case that describes the product. **Restriction of range** is the name for what gating does.
A rating system never measures difficulty directly; it only observes *comparisons*, and the whole
scale is assembled from overlapping ones. If every comparison in your data is between things
already close together, you have plenty of information about local ordering and almost none about
distance across the range.

The staircase analogy: you must measure a staircase's total height, but the only measurement
allowed is a comparison between two *adjacent* steps. You learn local ordering beautifully, and you
get the total by chaining twenty comparisons — each carrying error, compounding along the chain,
with no observation ever spanning the whole staircase to check. That is a gated attempt log: no
attempt pairs a 25-kyu player with an sdk puzzle, so nothing ties the bottom of the scale to the top
except a long chain of local links.

In psychometrics this is the classic **test equating** or **linkage** problem. A gated tree is, in
effect, dozens of separate test forms — one per level band — administered to disjoint populations.

| first attempts/puzzle | ungated RMSE(off) | gated RMSE(off) | gated slope | gated ±100 | gated rho | gated/ungated |
|---|---|---|---|---|---|---|
| 3 | 329.2 | 442.0 | 0.53 | 20% | 0.23 | 1.3× |
| 5 | 290.7 | 409.0 | 0.94 | 19% | 0.39 | 1.4× |
| 10 | 247.2 | 403.6 | 1.17 | 19% | 0.41 | 1.6× |
| 20 | 200.0 | 368.1 | 1.89 | 22% | 0.63 | 1.8× |
| 40 | 164.0 | 348.5 | 2.63 | 24% | 0.78 | 2.1× |
| 80 | 128.1 | 314.5 | 2.67 | 24% | 0.89 | 2.5× |
| 160 | 104.0 | 279.1 | 2.35 | 29% | 0.95 | 2.7× |

**Be precise about the shape.** Gated error does **not** plateau. It falls steadily, by about 28
points per doubling, against 39 for ungated. The last doubling in the sweep still drops 35.4 points
(314.5 → 279.1) — a curve hitting a wall does not do that. Gating buys slower convergence, not a
ceiling.

Because it converges more slowly, the *ratio* widens with volume rather than closing: 1.6× at 10
attempts, 2.1× at 40, 2.7× at 160. In absolute points the deficit is roughly flat — 156, 185, 175 —
so more traffic improves both curves without the gated one catching up.

An earlier draft claimed a plateau. That was wrong, and the 80 and 160 rows refuted it. The
correction matters because the two diagnoses recommend opposite things. A plateau would say gated
data has a hard ceiling, more traffic is wasted, and the only lever is redesigning the product. A
slower slope with a widening ratio says more traffic does keep helping and a large gated log is
genuinely worth fitting — but you cannot buy parity with an ungated instrument, so pairing design
is a lever to pull *in addition to* volume. The second is the more useful finding, and it says the
existing history is not a write-off.

**Now the diagnosis, which is the real content.** At 160 attempts gated: rho 0.95, RMSE(off) 279.1,
slope 2.35. The estimator has essentially *solved the ordering* and is still nearly three ranks
off. RMSE(aff) is 138.9, just under half of RMSE(off), and that gap between the two metrics is the
fingerprint of scale error rather than noise. Slope 2.35 spells out the damage: two puzzles truly
470 points apart — a full standard deviation — are fitted about 200 points apart.

One curiosity worth reading: the gated slope at 3 attempts is 0.53, meaning the spread is nearly
twice too *wide*. With three attempts a rating is a couple of coin flips from its 1500 start, so
fitted values scatter beyond the truth. Compression only sets in once there is enough data for the
estimator to start believing its neighbours.

### Online versus a joint fit

That table is a fact about *online Glicko-2 on gated data*. It is not yet a fact about gated data.
Separating the two is what `batch_fit.py` is for, and the separation turned out to be most of the
finding.

**The mechanism.** An online estimator processes attempts one at a time, using only what it knows
at that moment. Early in the log every player and puzzle sits at 1500 with RD 350, so the first
thousand updates compare two things that are both unknown — a strong player solving an easy puzzle
produces the same update as a weak player solving a hard one. Those early guesses then serve as the
reference for the next attempt.

Under ungated pairing that injected error washes out, because every competitor eventually meets
opponents from all over the range. Under gating it does not: information propagates only along the
chain of adjacent bands, so an early mistake in one band is only ever re-tested against that band's
neighbours. There is nothing distant to correct it against.

A **joint fit** has no such problem because it has no order. It takes the whole *bipartite graph* —
two kinds of node, players and puzzles, every edge one attempt — and solves for all 3,000 skills
and 300 difficulties simultaneously against one objective. No attempt is "first".

**What the joint fit is.** A **Rasch model**, the one-parameter model from **item response theory**
(IRT). IRT models the probability a particular person answers a particular item correctly as a
function of the person's ability and the item's properties; Rasch is the simplest member, where the
only item property is a single difficulty number:

```
P(person solves item) = 1 / (1 + exp(-(theta - beta)))
```

That is algebraically the same logistic-of-a-difference the simulation generates from, converted by
the single constant `SCALE`. So the batch fit is **correctly specified** — handed the true
generating model — which makes its numbers a best case, deliberately.

**Why MAP rather than MLE.** Maximum likelihood picks the parameters making the observed outcomes
most probable and nothing else. Maximum a posteriori adds a prior penalising implausibly extreme
values. The prior here is not a refinement, it is a requirement: a player with a single attempt is
**perfectly separated** — they either solved their one puzzle or did not, and either way the
likelihood keeps improving as you push their skill toward ±infinity. The unregularised maximum does
not exist. At 10 attempts per puzzle the log holds 3,000 attempts over 3,000 players, an average of
one each, so perfect separation is the common case, not an edge case.

**The comparison**, both estimators handed one list from a single `make_log` call and scored on the
same subset:

| attempts | regime | estimator | RMSE(off) | RMSE(aff) | slope | rho |
|---|---|---|---|---|---|---|
| 10 | ungated | online | 247.2 | 211.8 | 1.48 | 0.88 |
| 10 | ungated | batch | 237.4 | 212.4 | 1.37 | 0.88 |
| 10 | gated | online | 403.6 | 402.4 | 1.17 | 0.41 |
| 10 | gated | batch | **383.1** | 380.0 | 1.27 | 0.50 |
| 40 | ungated | online | 164.0 | 116.4 | 1.37 | 0.97 |
| 40 | ungated | batch | 129.1 | 105.2 | 1.21 | 0.97 |
| 40 | gated | online | 348.5 | 271.1 | 2.63 | 0.78 |
| 40 | gated | batch | **240.7** | 139.4 | 1.87 | 0.95 |
| 160 | ungated | online | 104.0 | 75.8 | 1.20 | 0.99 |
| 160 | ungated | batch | 62.8 | 50.9 | 1.09 | 0.99 |
| 160 | gated | online | 279.1 | 138.9 | 2.35 | 0.95 |
| 160 | gated | batch | **102.8** | 38.7 | 1.28 | 1.00 |

Read the last two rows first. On gated data at 160 attempts, online Glicko-2 sits at 279.1 with its
scale compressed 2.35×. The joint fit, on **the identical log**, reaches 102.8 with slope 1.28 — a
**63% cut**, with most of the compression gone and rho at 1.00. The chain-of-local-links problem is
still in the data; the joint fit solves the whole chain at once instead of walking it in one pass.

Then the 10-attempt gated rows: 403.6 to 383.1. The joint fit buys 20 points out of 400, about 5%.
At that volume there is nothing for a better estimator to extract.

**Is it really sequentiality, or just a different likelihood?** A fair objection: the two arms
differ in *two* ways, not one. Online Glicko-2 uses `g`-flattening, volatility and clamps; the batch
arm is plain Rasch with none of them. So the comparison could be measuring the likelihood rather
than the fitting strategy. Isolating it needs a third arm — the *same* Rasch model fitted
sequentially, by one chronological pass of stochastic gradient descent, best of five learning rates
to give it its best shot:

| attempts | regime | online Glicko-2 | online Rasch | joint Rasch |
|---|---|---|---|---|
| 40 | gated | 348.5 (slope 2.63) | 404.8 (slope 3.42) | 240.7 (slope 1.87) |
| 40 | ungated | 164.0 (slope 1.37) | 313.1 (slope 2.08) | 129.1 (slope 1.21) |
| 160 | gated | 279.1 (slope 2.35) | 390.4 (slope 4.76) | 102.8 (slope 1.28) |
| 160 | ungated | 104.0 (slope 1.20) | 316.2 (slope 2.50) | 62.8 (slope 1.09) |

The answer is unambiguous, and it favours the conclusion. Holding the likelihood fixed at Rasch,
going from sequential to joint takes 390.4 to 102.8 — the whole effect. And Glicko-2's extra
machinery *helps* the sequential arm rather than explaining its weakness: 279.1 against naive
sequential Rasch's 390.4. So sequentiality is the cause, Glicko-2 is a good sequential estimator,
and a joint fit beats any sequential one on this data. (Caveat: this crude SGD arm is not the best
possible sequential Rasch estimator, so treat it as bracketing the question rather than settling
the last word.)

### The honest three-way split

- **At low volume the penalty is real and estimator-independent.** At 10 attempts the joint fit
  buys almost nothing (403.6 → 383.1) and gated remains about 1.6× worse. This is an information
  limit in the data. No estimator recovers it, and no prior setting does either.
- **At useful volume the penalty is mostly an artefact of estimating online.** At 160 attempts, 176
  of the 279 points of gated error — 63% — are the sequential pass, not the pairing design.
- **It does not vanish.** At 160 attempts the joint fit is 102.8 gated against 62.8 ungated: a
  residual 1.6× that belongs to the data.

### RD is over-confident, and worst exactly where you would rely on it

Section 2 sold RD as the per-puzzle readiness gate — the number that answers "is this label ready
to show?". That recommendation needs testing, because RD is the estimator's claim about its own
accuracy and nothing so far has checked the claim against the accuracy. Comparing the two:

| attempts/puzzle | regime | mean reported RD | actual RMSE(off) | actual / reported | slope |
|---|---|---|---|---|---|
| 10 | ungated | 159.0 | 247.2 | 1.55× | 1.48 |
| 10 | gated | 154.8 | 403.6 | **2.61×** | 1.17 |
| 40 | ungated | 101.5 | 164.0 | 1.61× | 1.37 |
| 40 | gated | 91.4 | 348.5 | **3.81×** | 2.63 |
| 160 | ungated | 92.2 | 104.0 | 1.13× | 1.20 |
| 160 | gated | 77.4 | 279.1 | **3.61×** | 2.35 |

Two things to take from this.

**RD is over-confident everywhere, and mildly so when ungated.** At 160 ungated attempts it reports
92 and delivers 104 — a 13% understatement, which is about as honest as you could ask.

**Under gating it is dangerously over-confident, and the failure runs the wrong way.** At 160 gated
attempts RD reports **77 points** — *tighter* than the ungated case — while the actual error is
279. It is 3.6× more wrong than it admits, and it is *most* confident exactly where it is *least*
accurate. The mechanism is the same restriction of range: the estimator sees many mutually
consistent comparisons against nearby opponents, and mistakes local agreement for global precision.
Nothing in Glicko-2 can detect that the comparisons were selected, so it reports the precision it
would have earned had they been representative.

The consequence for the section-2 recommendation is direct: **on gated data, an RD threshold is not
a safe readiness gate.** It would pass labels that are three ranks off while reporting sub-rank
confidence. If you want a readiness gate, calibrate RD against realised error on a set of anchor
items — or gate on the ungated instrument's RD, which is nearly honest.

### The prior is not a free knob

Because the joint fit is MAP, someone can reasonably ask whether its advantage was bought with a
convenient prior: prior strength controls shrinkage, shrinkage *is* scale compression, and scale
compression is exactly what RMSE(off) measures. A tuned prior would be a thumb on the scale in the
most literal sense.

So it is derived, not tuned. `DEFAULT_L2 = (SCALE / TRUE_SD) ** 2` — a Gaussian prior whose
standard deviation *is* the planted population's standard deviation, which works out to **0.1386**.
That is a quantity a real operator can estimate from their own rating distribution without knowing
any individual truth, which is the whole difference between deriving and tuning.

`--l2` is exposed so the sensitivity can be checked. Gated, joint fit, RMSE(off):

| l2 | 160 attempts/puzzle | 10 attempts/puzzle |
|---|---|---|
| 0.1386 (derived default) | 101 (slope 1.27) | 385 |
| 0.05 | 41 (slope 1.06) | 366 |
| 0.03 | 33 (slope 1.00) | 364 |

(The 160-attempt cell reads 101 here against 102.8 in the table above because this sweep passes
`--l2 0.1386` rounded, where the default is the unrounded `(SCALE/TRUE_SD)²`. Adam is mildly
sensitive to that in the last digit.)

Both conclusions strengthen the section above rather than weakening it.

**The default is the pessimistic end.** Weakening the prior lets the fitted scale expand toward the
truth — slope 1.27 → 1.06 → 1.00 — and error at 160 attempts collapses from about 100 to 33. So the
reported 63% batch advantage is a **lower bound**; a tuned prior would make the gap larger. The
default is kept anyway, because a bound you can defend beats a better number obtained by looking at
the answer.

**The low-volume limit is not a prior artefact.** The 10-attempt cell moves 385 → 366 → 364 across
a 4.6× change in prior strength. Whatever is missing at 10 attempts per puzzle is missing from the
data, not from the regularisation.

### Linking items

A **linking item** — also a common item, or an *anchor* item when its difficulty is already
established — is an item served to everybody across the whole ability range. Its job is not to be a
good question; its job is to be a shared measurement point, so that a 25-kyu player and a 3-dan
player who both attempted it pin their otherwise-disconnected regions of the scale to a common
reference. On the staircase, it is being allowed one measurement from the ground floor to a step
halfway up.

Dose-response at 40 first attempts per puzzle, online Glicko-2:

| ungated fraction | RMSE(off) | slope | rho |
|---|---|---|---|
| 0% | 348.5 | 2.63 | 0.78 |
| 25% | 280.6 | 1.75 | 0.88 |
| 50% | 234.4 | 1.57 | 0.92 |
| 100% | 164.0 | 1.37 | 0.97 |

Monotone, no threshold to exploit, clear diminishing returns: the first 25% buys 68 RMSE points,
the next 47, the top half about 35 per 25%. Most of the scale compression goes with it (2.63 →
1.37), which is the expected signature — linking items attack the scale, precisely the part gating
damaged. The 100% row reproduces the ungated row exactly (164.0 / 1.37 / 0.97), the consistency
check that the knob does what it claims.

**Linking is second-order next to choosing the estimator, and still matters.** A joint refit buys
176 RMSE points at 160 gated attempts and costs only compute; 25% linking at 40 attempts buys 68
points and costs a quarter of your traffic being served off-tree. On pure return, refit first. But
a joint fit only ever describes *history*. The label a user sees the moment they finish a puzzle
comes from the live path, and the live path is online by necessity. Linking is the fix that
improves the number the live estimator produces.

Go Magic appears to already own the ungated instrument. **Go Diagnostics** (`/go-tests/`, in beta)
is not gated by the tree, which makes it structurally a linking instrument, and it is described as
returning *"an estimated puzzle rank with a confidence range"* — a confidence range around a rating
estimate being Glicko's RD under another name. (That quote is not backed by the committed snapshot;
see section 1.)

### The figure

`./src/recovery.py --puzzles 300 --reps 2` writes `out/recovery.png`: the three RMSE(off) curves
against log attempts, with the 100-point one-rank line marked. It is the fastest way to see that
the gated curve declines rather than flattening, which is the claim an earlier draft got wrong.

### What to actually do

1. **For a one-off backfill over existing history, fit jointly — and do not conclude from an online
   pass that the data is inadequate.** The largest and cheapest win here. Online Glicko-2 over gated
   history reports 279 RMSE where the *same log* supports 103, with compression mostly gone. An
   online pass over history measures what a sequential estimator extracts in one pass, not what your
   log contains. Before deciding 10,160 hand labels cannot be replaced, run the joint fit.
2. **Reserve online Glicko-2 for the live path, and seed it from the last joint refit.** Online is
   right live: constant work per attempt, no refit, and it produces RD. Its specific weakness is the
   cold-start chain, which a periodic joint refit removes by re-initialising the online state to
   ratings the whole graph supports. **One operational gap to close first:** `fit()` returns only
   skills and difficulties — a Rasch fit has no RD and no volatility. Reseeding therefore needs a
   deliberate choice of what uncertainty to restart from; setting RD to the floor freezes the online
   path, and setting it to 350 discards the refit's precision. The principled answer is to derive
   each puzzle's RD from its attempt count in the fit, which this repo does not implement.
3. **Route some traffic through an ungated instrument.** At 40 attempts per puzzle, 25% ungated
   buys 68 RMSE points and pulls slope from 2.63 to 1.75; 50% buys 114. Diminishing returns mean a
   modest fraction captures most of the value, so this does not require redesigning the tree. It is
   the only fix here that improves the *live* number. Go Diagnostics is plausibly already this
   instrument, so the question may be routing volume through something that exists.
4. **Consider anchoring the player side too — it is cheaper than re-routing traffic.** Linking items
   supply scale information through *puzzles* seen by everyone. The same information can come
   through *people*: if a player's rank is known independently — self-reported at signup, or from a
   diagnostic result — seeding their `theta` from it injects the same cross-range constraints
   without moving any traffic off-tree. This repo does not measure it, so treat it as the obvious
   next experiment rather than an established result.
5. **Decide the outcome definition — first life versus within lives — deliberately, and once.**
   The two produce different difficulty scales; a system that mixes them measures neither. Section 4
   lays out the trade-off; first-life-only is the more defensible default because "within allowed
   lives" is not even constant across a catalogue granting one or two. Post-failure retries must be
   excluded either way.
6. **Do not use an RD threshold as a readiness gate on gated data.** This is the recommendation the
   RD table above overturns. RD looks like the right per-puzzle answer, and on ungated data it
   nearly is (1.13× at 160 attempts), but on gated data it is 3.6× over-confident and *tightest*
   where it is least accurate. Either calibrate RD against realised error on anchor items, or take
   the readiness signal from the ungated instrument.
7. **Monitor the scale, not the correlation.** The dominant failure on gated data is scale
   compression with near-perfect ordering: rho 0.95 with slope 2.35. Any dashboard built on
   correlation or a scale-free error would have shown that as a success, and an earlier draft of
   this work reached the wrong conclusion by exactly that route. Track a scale-preserving error and
   a fitted slope against anchor items of known difficulty.
8. **Also fix the label mapping, which this repo does not address.** Every number here is a rating.
   The product ships an 11-level table, so replacing it needs cut points from the rating scale onto
   levels — and the compression finding bears directly on that: fitted values 2.35× too narrow
   pushed through fixed cut points collapse the catalogue toward the middle levels, which would look
   like "most puzzles are intermediate" rather than like an estimator bug. Define the cut points
   from the *fitted* distribution's quantiles rather than from absolute rating thresholds, or fix
   the scale first.

---

## 8. Glossary

### Go and the product

- **Go (baduk)** — the board game the puzzles come from.
- **kyu / dan** — the rank ladder. Kyu counts *down* toward stronger (20k is weaker than 1k); dan
  counts up above that.
- **rank ≈ 100 rating points** — the conversion used throughout.
- **tesuji** — a local tactical move that achieves more than it looks like it should.
- **nakade** — a shape whose interior can be killed by taking its vital point.
- **joseki** — an established sequence, usually in a corner.
- **skill tree / node / level / quiz** — Go Magic's progression structure: 74 nodes, 1–5 levels
  each, 2–6 quizzes per level, 5 puzzles per quiz.
- **attempt slot** — one (puzzle, position-in-tree) opportunity; 4,790 to complete the tree.
- **lives** — the one or two tries granted per puzzle; a retried solve earns no coins or XP.
- **Go Diagnostics** — Go Magic's ungated blind test at `/go-tests/`, in beta.
- **lila** — the Lichess server codebase, source of the production constants used here.

### Rating systems

- **Elo** — rating system in which only the *difference* between two ratings determines the outcome
  probability.
- **K-factor** — Elo's single global step size, the same for every competitor.
- **logistic curve** — the S-shaped function mapping a rating difference to a probability.
- **log-odds** — the natural logarithm of `p/(1-p)`; the units Glicko-2 works in internally.
- **rating** — the point estimate of strength; 1500 by default.
- **rating deviation (RD)** — the uncertainty about a rating, in rating points; roughly a 95%
  interval of rating ± 2·RD.
- **volatility (sigma)** — how erratic a competitor's results have been; the quantity Glicko-2 adds
  over Glicko.
- **tau** — the system constant bounding how much volatility may change in one rating period (0.75
  here, 0.5 in Glickman's example).
- **rating period** — a batch of games all scored against the ratings as they stood at its start.
  One attempt, here.
- **mu / phi** — rating and RD converted to the internal natural-log scale.
- **SCALE** — `400/ln(10)` = 173.7178, converting between the Elo scale and the internal one.
- **g(phi)** — the factor shrinking an opponent's contribution when their own rating is poorly
  known.
- **expected score (E)** — the model's predicted probability that one competitor beats the other.
- **v** — the variance the games in a period imply. Small v means informative games.
- **delta / delta_sum** — the move the games alone suggest, and the raw `g`-weighted
  actual-minus-expected residual it is built from.
- **phi_star** — the pre-game deviation inflated by volatility.
- **in quadrature** — combining two independent quantities as `sqrt(a² + b²)`.
- **precision** — reciprocal variance. Precisions add when independent evidence is combined.
- **regula falsi / Illinois variant** — the root-finding method used for the volatility update:
  draw a line through two bracketing points, take its zero crossing, and halve the retained
  endpoint's value to avoid one-sided stalling.
- **bracket** — a pair of points whose function values have opposite signs, so a root lies between.
- **clamp** — a hard bound on an output (`MIN_DEVIATION` 45, `MAX_DEVIATION` 500,
  `MAX_VOLATILITY` 0.1, `MAX_RATING_DELTA` 700).
- **saturation** — the point at which `exp()` of a large gap rounds an expected score to exactly 0
  or 1, so the implied variance underflows. Around 6,447 rating points here.
- **first attempts only** — one observation per (player, puzzle) pair, the first. Retries measure
  recall, not difficulty.
- **hint damping / weight** — applying only a fraction of an update when the presentation gave
  something away.

### The experiment and its measurement

- **planted world / ground truth** — the true skills and difficulties the simulation draws and
  keeps as the answer key.
- **seed / rep** — the RNG seed making runs reproducible; a rep is one planted world.
- **band / banded / gated** — the regime in which a player only meets puzzles within `band` (300)
  points of their own level.
- **ungated / random pairing** — any player may meet any puzzle; the diagnostic-test regime.
- **restriction of range** — the degradation that follows when every observed comparison is between
  things already close together.
- **test equating / linkage** — placing scores from separately-administered tests on one scale.
- **linking item / common item / anchor item** — an item served across the whole ability range so
  disconnected regions of the scale are pinned to a shared reference; "anchor" when its difficulty
  is already established.
- **identifiability** — whether different parameter values imply different distributions over the
  data. The origin of the difficulty scale is *not* identifiable here.
- **degeneracy** — a direction in parameter space the data cannot see; here, adding a constant to
  every skill and every difficulty.
- **item response theory (IRT)** — modelling the probability a given person answers a given item
  correctly.
- **Rasch model** — the one-parameter IRT model, `p = sigmoid(theta - beta)`. One ability per
  person, one difficulty per item, only the difference matters.
- **latent trait** — the unobserved quantity (skill, difficulty) inferred from outcomes.
- **misspecification** — a mismatch between the process generating the data and the model fitted to
  it. Absent here by construction.
- **online estimator** — processes attempts one at a time in log order, using only what is known at
  that moment.
- **joint / batch fit** — solves for all parameters at once against the whole log. No notion of
  order.
- **bipartite graph** — a graph with two kinds of node (players, puzzles) and edges only between
  kinds; one edge per attempt.
- **MLE / MAP** — maximum likelihood (fit the data only) versus maximum a posteriori (fit the data
  plus a prior).
- **Gaussian prior / L2 penalty** — a normal prior on the parameters, appearing in the gradient as
  a term proportional to the parameter itself, with weight `1/sd²`.
- **perfect separation** — a competitor whose observations are all wins or all losses, so the
  unpenalised likelihood improves without limit toward infinity.
- **shrinkage** — the pull of a prior toward the mean. Too much of it is scale compression.
- **Adam** — gradient descent with a per-parameter adaptive step size.
- **RMSE** — root mean squared error; an average error in rating points that penalises large misses
  more than small ones.
- **RMSE(off)** — RMSE after removing only a mean offset. Keeps the fitted scale, so compression
  counts as error. The primary number.
- **RMSE(aff)** — RMSE after removing a full least-squares affine map fitted against the truth.
  Equals `sd(truth)·sqrt(1-r²)`, so it is blind to scale error.
- **slope** — the affine slope from that fit. 1.0 means the fitted scale is right; 2.35 means the
  fitted spread is 2.35× too narrow.
- **scale compression** — right ordering, understated spacing.
- **within ±100** — the share of puzzles inside one rank, under the offset-only alignment.
- **Spearman rho** — correlation of ranks; measures ordering only.
- **Pearson r** — correlation of values; measures linear agreement.
- **oracle metric** — one whose alignment is fitted against the truth, so it reports a number no
  production system could realise.

### Further reading

- Mark E. Glickman, *Example of the Glicko-2 system* — `glicko.net/glicko/glicko2.pdf`. The eight
  steps and the worked example `tests/test_glicko2.py` validates against.
- Glickman's earlier Glicko paper, for where RD comes from and why.
- Any introduction to item response theory for the Rasch model, test equating, and common-item
  linking designs — the vocabulary sections 6 and 7 borrow.
