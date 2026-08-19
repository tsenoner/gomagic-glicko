# Go problem sources: the precedent, the licences, and what can actually be collected

Two questions, answered by a twelve-agent survey with an adversarial licence-verification pass
(2026-08-17/18):

1. **Has anyone already derived Go puzzle difficulty from attempt data?**
2. **What Go problems are freely and legally reusable, and how do they map onto Go Magic's grid?**

Machine-readable companions: [`data/problem_sources.json`](../data/problem_sources.json) (every
source checked, with licence and verdict) and [`data/taxonomy_map.json`](../data/taxonomy_map.json)
(external tag → `(phase × concept)` cell, plus the coverage matrix).

---

## 1. The precedent answer: yes, and it predates this project by ~25 years

This is the correction the repo most needed. **Treating a Go puzzle as a rated competitor and
updating it from attempts has been production practice since roughly 1999.** Any framing of this
work as "nobody has tried this" would not survive five minutes with a Go audience.

| Site | Derives difficulty from attempts? | Mechanism |
|---|---|---|
| **goproblems.com** | **Yes** | Elo. Problem and user both rated, each attempt scored as a match. Per-problem K decays from ~127 on a fresh problem toward ~10 once heavily attempted. |
| **Tsumego Hero** | **Yes** | **EGF GoR**, not Elo or Glicko. Both sides update every attempt; each misplay is processed as a separate loss before the eventual solve. Problem ratings clamped to admin-set bounds. |
| **101weiqi.com** | **Probably — undocumented** | Problem difficulty sits on the *same numeric axis* as player rating, with a 30-bin pass/fail histogram binned by solver rating — an empirical item-characteristic curve. The update rule is published nowhere. Hedge this. |
| **OGS** | **No** | The author types a rank into a dropdown. `attempt_count` and `solved_count` are stored and never used. |

The **exact** methodological precedent is out of domain: Lichess states that each solve attempt is
treated as a Glicko-2 rated game between player and puzzle — line for line this project's design,
at ~6.1M puzzles, published CC0 with per-puzzle rating, deviation and play count. It is the only
freely reusable attempt-rated puzzle dataset in existence, and it is chess.

### So what is left that is genuinely this project's own?

Honest accounting, because over-claiming here is the fastest way to lose credibility:

**Already done elsewhere — do not claim.** Puzzle-as-competitor; one shared axis for difficulty and
strength; gating a derived rating on stability before trusting it; admin clamps against drift;
counting misplays as separate losses; lives mechanics that censor the log (Tsumego Hero implements
the exact mechanic this repo models).

**Genuinely open, and defensible:**

1. **Glicko-2 rather than Elo/GoR.** Neither Go implementation carries an explicit rating deviation
   or volatility. goproblems' decaying K *behaves* like an RD but does not fit a clean function of
   attempt count — which is an argument *for* modelling RD explicitly rather than approximating it
   with a K schedule, and it gives a principled stopping rule where goproblems has a heuristic gate.
2. **Anchoring, which is unsolved in the wild.** Sampling goproblems' full rating histories shows
   real lifetime drift, mostly downward. Tsumego Hero's clamps and EGF's bonus term are two
   independent, converged answers to the same deflation problem. A hand-assigned seed *as a prior*
   plus bounds is the pattern both mature systems arrived at — which is exactly the
   "use the 11-level labels as the item prior" item in [`TODO.md`](../TODO.md).
3. **Doing it under a gated skill tree**, where the sample is censored by progression *and* by a
   lives mechanic. Nobody has published on this.
4. **A 3×5 concept grid.** No site does per-cell difficulty estimation; all use one flat genre list.

**The strongest single argument that this is wanted:** OGS has had an open issue for
*Glicko rating for puzzles* since **February 2022**, motivated by puzzles having "static, often
outdated ratings", still unimplemented — while already recording the attempt counts it would need.

---

## 2. What is actually reusable

**3,982 Go problems**, from four sources. That is the honest total, and most of it is unusable in a
paid product.

| Source | Problems | Difficulty metadata | Licence | Catch |
|---|---|---|---|---|
| Sensei's Library wiki dump | 2,857 | **Best anywhere**: a 6-value difficulty enum plus phase/concept keywords | Open Content License 1.0 | Forbids charging for network access; copyleft is viral over the whole derivative |
| Gokyo Shumyo, 1912 (NDL) | 520 | None — seven topical sections, ungraded | Public Domain Mark | Page scans, not SGF |
| Go Game Guru weekly problems | 422 | 3 bands (easy/intermediate/hard), evenly split | CC BY-NC-SA | NonCommercial; ShareAlike is incompatible with this repo's MIT licence |
| Igo Hatsuyoron, 1914 (NDL) | 183 | None | Public Domain Mark | Page scans, not SGF |

Plus **Lichess's CC0 puzzle database** — 6.1M chess puzzles with Glicko-2 ratings, deviations and
play counts. Useless as Go content; invaluable as the one place to validate this project's method
against real crowd-derived ratings.

**Thirteen further sources were checked and rejected**, listed in the JSON so they are visibly
checked rather than silently missed. Two warnings are worth repeating here:

> **A public-domain position does not make a machine-readable file of it public domain.** Gokyo
> Shumyo (1812), Xuanxuan Qijing (1349) and Igo Hatsuyoron (1713) are public domain as *works*.
> Every convenient SGF transcription carries either no licence, a code-only licence, or added
> solution trees that are new copyright. Re-keying from a public-domain scan is the only clean-room
> route.

> **Compilation copyright is real.** Selecting and arranging problems by difficulty or theme is a
> creative act in many jurisdictions, so copying a whole published collection can infringe the
> compiler's rights even when every position in it is ancient.

Several rejected sources look safe and are not — including one whose MIT-style licence file grants
rights only in "the Software" while the repository is wholesale digitisations of in-print books,
and one assembled by scraping a commercial site through a rotating Tor proxy to evade IP bans.
Neither should be used or mirrored.

---

## 3. The taxonomy problem

**No external source emits a `(phase, concept)` pair.** goproblems and OGS share an identical
seven-value flat vocabulary: *elementary, life and death, joseki, fuseki, tesuji, best move,
endgame*. Of those, three give only phase, two give only concept, one is a difficulty band
misfiled as a category, and one says nothing at all. Since tesuji and life-and-death together are
~92% of those corpora, **~92% of any import arrives with the phase axis blank.**

The full mapping is in `data/taxonomy_map.json`. Three things worth surfacing:

- **`joseki` is the only external tag that lands in exactly one cell with no inference**
  (opening × knowledge). Everything else needs a judgement.
- **The biggest judgement call** is the ~20 named group statuses (carpenter's square, bulky five,
  bent four…). They are genuinely dual: *knowledge* when the puzzle tests recall of the status,
  *life-and-death* when it tests reading it out. No external site makes this distinction, and the
  decision reassigns thousands of problems.
- **Phase is recoverable from the SGF** — stone count, board size, corner/side/centre contact,
  whether surrounding groups are settled. `src/build_collection.py` ships a deliberately crude
  first cut; see below for how badly it does.

### Coverage: where free material simply does not exist

From the reusable set only — **2 cells saturated, 1 good, 2–3 moderate, 4 thin, 3 near-empty, 1
empty:**

| | fighting | tesuji | life-and-death | analysis | knowledge |
|---|---|---|---|---|---|
| **opening** | near-empty | near-empty | **empty** | thin | puzzle-poor |
| **middle-game** | good | **saturated** | **saturated** | thin | weak |
| **endgame** | near-empty | thin | thin | moderate | thin |

**The entire opening row is where free material does not exist** — and that is precisely where Go
Magic's hand-authored catalogue is differentiated, *and* the row a Glicko-2 recovery will have
least attempt data for, because a gated tree serves opening nodes last. Three findings converging
on one cell is the most actionable thing in this document.

---

## 4. Difficulty labels cannot be merged as published

The four reusable sources grade on incompatible schemes — a 6-value editorial enum, a 3-band
editorial split, and two ungraded classical collections. Nothing published equates them, and the
populations differ. Putting them on one scale requires the same machinery as the rest of this
repo: **common items solved by a common population**, i.e. test equating, not a lookup table.

This is why `build_collection.py` keeps each source's own label verbatim in `difficulty_band` and
leaves `difficulty_rank` null. Inventing a kyu value for "intermediate" would be exactly the
unearned precision the rest of the project argues against.

---

## 5. Using it

```sh
./src/build_collection.py --list        # sources and licences
./src/build_collection.py --fetch ggg   # 422 SGF -> out/collection/ (NOT committed)
./src/build_collection.py --index       # normalise onto the grid
```

The repo ships the **index and the fetcher, never the content**: the two open Go sources carry
terms this MIT repo cannot absorb, so `out/collection/` is gitignored and you acquire the problems
under their licence rather than ours.

**A result worth reporting from the first run:** the phase classifier assigns 421 of Go Game Guru's
422 problems to middle-game. That is not really a classifier failure — it is the coverage matrix
showing up in data. Weekly problems are local shape problems with many stones on the board, and the
opening row is empty in the free corpus for the same reason it is empty in the table above.
