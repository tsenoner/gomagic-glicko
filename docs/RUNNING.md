# Running it

Every table in [`FINDINGS.md`](FINDINGS.md) is one of these commands at its printed defaults, seed
included.

```sh
./tests/test_glicko2.py                                  # §2  validate the estimator against Glickman's worked example
./tests/test_parse_tree.py                               # §1  pin the published skill-tree inventory
./src/parse_tree.py --html data/skilltree-2026-08-16.html # §1  the inventory, offline from the snapshot
./src/parse_tree.py --json out/tree.json                 # §1  or fetch the live public page
./src/recovery.py --quick                                #     fast sweep, for iterating
./src/recovery.py --puzzles 300 --reps 10                # §3  gated vs random, online and joint; writes out/recovery.png
./src/batch_fit.py --puzzles 300 --reps 10               # §4  online vs joint fit, on the same log
./src/recovery.py --puzzles 300 --reps 10 --sweep 40 --linking 0.25 0.5 1.0 --out /tmp/linking.png  # §5
./src/recovery.py --puzzles 300 --reps 10 --sweep 40 160 --funnel 0.02 --out /tmp/funnel.png       # §7
./src/egd_scale.py --selftest                            #     the rank-scale arithmetic, no network
./src/egd_scale.py                                       #     re-measure what one rank is worth, from EGD
```

`egd_scale.py` is the odd one out: it measures real Go, not the simulation. It re-derives every
number in [`RESEARCH.md`](RESEARCH.md) §1 from the European Go Database's published statistics —
the ~675k-game even-game tables, the ~1.05M-game calibration table, and the active ladder. A cold
run takes ~12 minutes, because each of the eleven windows is a server-side aggregate that EGD needs
about a minute for, fetched sequentially to stay polite. Responses cache under `out/egd/` and are
not committed. EGD is live, so counts grow slowly over time; the figures quoted in the docs were
taken on 2026-09-01.

Each script carries its own [PEP 723](https://peps.python.org/pep-0723/) inline dependency header,
so `uv` resolves what it needs on the spot — **there is no environment to set up and no checkout
required to run one file.**

## Three things to know before changing the flags

- **The joint refit rides along.** The default run also fits each gated and ungated log jointly,
  which is what the dashed curves are and what makes the chart carry section 4 as well as section
  3. It roughly triples the runtime, to about 50 seconds; `--no-joint` skips it. The rows it prints
  match `batch_fit.py` digit for digit, since both call the same `fit` on the same log.
- **`--reps` drives the confidence intervals.** Below 2 they are undefined; 10 is what every
  published table uses, and the cost is linear.
- **`--sweep` takes the attempts-per-puzzle points directly.** Read its `--help` before pushing past
  160: `make_log`'s nearest-N band fallback silently ungates the simulation unless `--players` grows
  with it, which makes the gating penalty look like it evaporates. [`FINDINGS.md`](FINDINGS.md) §3
  documents the trap.
- **The two `--sweep` commands pass `--out` explicitly** because the default would overwrite the
  committed `out/recovery.png`, the full-sweep chart the one-pager embeds, with a one- or two-point
  plot.

With `--funnel` the script also runs each regime's flat twin and prints the paired funnel-vs-flat
cost, which is where §7's "paired cost" column comes from.

## The dev loop

A project definition exists for it (Python **3.12+**):

```sh
uv sync                # dev environment, from uv.lock
uv run ruff check .    # lint
./tests/test_glicko2.py
```

Ruff lints but does not format. The scripts are written to be read — the module docstrings are the
`--help` text, the Adam update is aligned one step per line, the table prints line their columns up
in the source — and the formatter reflows all of it.

CI runs `ruff check`, both test suites, a build of [`METHOD.md`](METHOD.md) and of the one-pager,
the problem-source manifest check, a smoke run of both experiments, and a standalone run of
`test_glicko2.py` outside the project environment to prove the PEP 723 path still works. The
inventory assertion pins 74 / 35 / 23 / 4,790 so the published numbers cannot drift silently.

## Layout

```
src/glicko2.py          Glicko-2 + Lichess production rules
src/recovery.py         the planted world, the attempt log, online fitting, scoring, the plot
src/batch_fit.py        joint Rasch MAP refit of the same log, to test the online artefact
src/parse_tree.py       public skill-tree parser
src/build_collection.py fetches openly-licensed Go problems onto the 3x5 grid (content untracked)
src/egd_scale.py        measures what one Go rank is worth, from EGD (responses untracked)
tests/                  Glickman's worked example, the clamps, and the pinned tree inventory
data/                   the public page snapshot, the problem-source audit, the taxonomy map
docs/build.py           renders METHOD.md into out/method.html (a reading view)
docs/onepager.py        renders the one-page summary into out/onepager.pdf
docs/assets/            that page's stylesheet and script, as real files
NOTICE                  third-party content: the page snapshot, and what is Lichess's
```

`recovery.py` owns the shared pieces — `make_log` builds the attempt log, `replay` fits it online,
`score_values` computes both error metrics — so `batch_fit.py` scores a different estimator on the
same log rather than re-deriving its own.
