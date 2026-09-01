#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Render the one-page summary to out/onepager.pdf.

    ./docs/onepager.py                  # HTML + PDF
    ./docs/onepager.py --html-only      # skip the browser step

The PDF is the project's outward-facing deliverable: one side of A4 that states the finding,
shows the one chart that carries it, and is explicit about what the work does *not* establish.
Everything in it traces to a number in this repo — see `docs/METHOD.md` for the derivations and
the sourcing table for which claims about Go Magic are backed by the committed page snapshot.

Rendering goes through headless Chrome rather than a PDF library so the layout is plain HTML and
CSS that can be opened, read and adjusted in a browser. The chart is inlined as a data URI, so the
intermediate HTML is a single self-contained file.
"""

from __future__ import annotations

import argparse
import base64
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The stylesheet is a real file, not a Python string, for the reasons docs/build.py states at
# its ASSETS constant: as a string no editor highlights it and a syntax error ships silently.
CSS_PATH = ROOT / "docs" / "assets" / "onepager.css"

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome",
    "chromium",
    "chromium-browser",
]


def find_chrome() -> str | None:
    # shutil.which resolves absolute candidates and PATH lookups alike.
    return next((w for c in CHROME_CANDIDATES if (w := shutil.which(c))), None)


def read_css() -> str:
    """The brace-balance guard from docs/build.py's `check_css`, duplicated in miniature:
    build.py imports the `markdown` package at module top and this script is dependency-free,
    so the five lines are copied rather than the import taken."""
    css = CSS_PATH.read_text()
    stripped = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    if stripped.count("{") != stripped.count("}"):
        sys.exit(f"{CSS_PATH.name}: unbalanced braces")
    return css


def data_uri(png: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(png.read_bytes()).decode()


def build_html(chart: str, css: str, built: str) -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Measuring Go puzzle difficulty</title>
<style>{css}</style></head><body>

<h1>Measuring Go puzzle difficulty</h1>
<p class="sub">How much attempt data does it take to <em>measure</em> a puzzle's difficulty,
instead of assigning it by hand?</p>
<div class="rule"></div>

<p class="setup"><strong>What I did.</strong> Plant 300 puzzles and 3,000 players with known
difficulties and skills. Simulate their first-attempt logs under three exposure patterns; the one
modelling Go Magic is skill-tree gating, where a player meets only puzzles within 300 points of
their own level. Fit the ungated and gated logs twice with the truth hidden: online, one attempt
at a time as a live system runs Glicko-2, and jointly, one Rasch fit of every rating at once.
Score both against the planted difficulties. Scale: <strong>&plusmn;100 points &asymp; one Go
rank</strong> (EGF convention; measured, a rank is 96 points at 1d and 44 at 10k); assigning
every puzzle the same difficulty scores 467 points of error.</p>

<div class="finding">
  <p class="lead">About 160 first attempts measure a puzzle's difficulty to roughly one rank,
  but on skill-tree data only if the log is fitted <em>jointly</em>. Replaying the same log
  one attempt at a time, the standard online way, leaves almost three ranks of error:
  <span class="num">287</span> points against <span class="num">112</span>, a
  <span class="num">61%</span> cut for nothing but compute.</p>
  <p class="note">So backfill the existing log jointly. The trap is replaying it online, reading
  287 points of error and calling the data inadequate.</p>
</div>

<div class="split">
  <figure>
    <img src="{chart}" alt="Difficulty recovery error against first attempts per puzzle, for
    ungated and gated logs fitted online and jointly">
    <figcaption><strong>Three exposure patterns, two estimators.</strong> Colour is the data:
    ungated random pairing against skill-tree gating, a &plusmn;300-point band standing in for
    Go Magic's row-by-row tree (which Gold and Magic members can switch off, so part of the real
    log is ungated); green, fitted online only, adds 25% ungated traffic. Line style is the
    estimator: solid online, dashed the same log refit jointly. Dotted lines: one-rank accuracy
    and the 467 ceiling. Bands: 95% intervals over ten simulated worlds.</figcaption>
    <p class="repro"><strong>Reproduce.</strong>
    <code>./src/recovery.py --puzzles 300 --reps 10</code> draws every curve here; the other
    numbers trace to <code>docs/RUNNING.md</code> and <code>METHOD.md</code> sections 1 and 7; the
    estimator is checked against Glickman's worked example. Go Magic facts are from the committed
    snapshot of its public skill-tree page (16 Aug 2026); nothing private.</p>
  </figure>
  <div>
    <h2>Three results</h2>
    <div class="stack">
      <div>
        <h3>Gating itself costs accuracy</h3>
        <p>Under gating no player's attempts span an easy puzzle and a hard one: against ungated
        pairing, <span class="num">1.6&times;</span> the error at 10 first attempts per puzzle,
        <span class="num">2.7&times;</span> at 160, and a coarser check holds about 2.8&times;
        out to 1,280. Neither more traffic nor a better estimator closes the gap to ungated data:
        refit jointly, <span class="num">1.75&times;</span> remains.</p>
      </div>
      <div>
        <h3>The damage is to the spacing, not the ordering</h3>
        <p>At 160 attempts the gated online fit ranks puzzles well but compresses the scale to
        under half its width: it knows <em>which</em> puzzle is harder, not <em>by how much</em>.
        The joint fit repairs most of it.</p>
      </div>
      <div>
        <h3>Uneven traffic is a second, separate cost</h3>
        <p>Everybody attempts the first row; few reach the last. At equal volume an assumed 50:1
        funnel costs <span class="num">30&ndash;50</span> points and drops the ordering, the one
        thing gating had left intact, from 0.94 to <span class="num">0.78</span>.</p>
      </div>
    </div>
    <table class="mini">
      <thead><tr>
        <th>at 160 first<br>attempts</th><th>RMSE</th>
        <th>compression</th><th>ordering &rho;</th>
      </tr></thead>
      <tbody>
        <tr><td>ungated, online</td><td>107</td><td>1.20</td><td>0.986</td></tr>
        <tr><td>ungated, joint</td><td>64</td><td>1.09</td><td>0.994</td></tr>
        <tr><td>gated, online</td><td>287</td><td>2.36</td><td>0.945</td></tr>
        <tr><td>gated, joint</td><td class="win">112</td><td>1.30</td><td>0.996</td></tr>
      </tbody>
    </table>
    <p class="tnote">RMSE in rating points, mean offset removed. Compression: the slope of
    planted on fitted difficulty; 1.0 is right, 2.36 means the fitted spread is 2.36&times; too
    narrow. &rho;: rank correlation. Ten-world means; each pair of rows fits the identical
    log.</p>
  </div>
</div>

<h2>What to do about it</h2>
<div class="cols">
  <div>
    <h3>Backfill jointly, serve online</h3>
    <p>Fit the history jointly for the labels, with one skill per player per time window: the
    joint fit otherwise holds a learner's skill fixed. Keep online Glicko-2 for the live path,
    where <span style="white-space:nowrap">one-at-a-time</span> updating is right.</p>
  </div>
  <div>
    <h3>Ship labels per puzzle, not per catalogue</h3>
    <p>Publish a measured label where enough attempts exist and keep the hand label until then,
    decided by count, not by Glicko's own error bar (RD), which under gating understates its error
    <span class="num">3.7&times;</span>.</p>
  </div>
  <div>
    <h3>Anchor the scale with an ungated test</h3>
    <p>An ungated test across the ranks is the standard repair for compression: 25% of traffic
    through one buys the online fit back <span class="num">57</span> points at 40 attempts and
    half the compression. Go Tests may already be one.</p>
  </div>
</div>

<div class="caveat">
  <strong>What this does not claim.</strong> Not that any hand label is wrong; that needs the
  private attempt log, and none is used here. It answers the question before that one: measured
  from attempts, how much data would a difficulty need to mean anything? Simulation can settle
  that for the estimator and the data's shape; real attempts fit its one-trait logistic model
  less well, so read the counts here as a floor.
</div>
<p class="next"><strong>The next step is small:</strong> fit one month of the real log both ways,
first attempts only (the try the coin rule singles out). If the table holds, the online labels come
out about half as wide as the joint ones, and attempts per puzzle place every label on the red curves
above.</p>

<footer>
  <span>Tobias Senoner &middot;
    <a href="https://github.com/tsenoner/gomagic-glicko">github.com/tsenoner/gomagic-glicko</a>
    &middot; {built}</span>
  <span>Method, derivations and sourcing:
    <a href="https://github.com/tsenoner/gomagic-glicko/blob/main/docs/METHOD.md"><code>docs/METHOD.md</code></a></span>
</footer>

</body></html>
"""

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--chart", type=Path, default=ROOT / "out" / "recovery.png")
    ap.add_argument("--out", type=Path, default=ROOT / "out" / "onepager.pdf")
    ap.add_argument("--html-only", action="store_true")
    ap.add_argument("--built", default=date.today().strftime("%-d %b %Y"),
                    help="the date printed in the footer (default: today)")
    args = ap.parse_args()

    if not args.chart.exists():
        sys.exit(f"missing {args.chart} — run ./src/recovery.py --puzzles 300 --reps 10 first")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    html_path = args.out.with_suffix(".html")
    html_path.write_text(build_html(data_uri(args.chart), read_css(), args.built))
    print(f"  wrote {html_path}")
    if args.html_only:
        return

    chrome = find_chrome()
    if chrome is None:
        sys.exit("no Chrome/Chromium found; open the HTML and print to PDF, or use --html-only")

    proc = subprocess.run(
        [chrome, "--headless", "--disable-gpu", "--no-pdf-header-footer",
         f"--print-to-pdf={args.out}", html_path.as_uri()],
        capture_output=True,
    )
    if proc.returncode != 0:
        # Chrome's own error is the diagnosable part; a bare CalledProcessError would hide it.
        sys.exit(f"Chrome exited {proc.returncode} rendering the PDF:\n"
                 f"{proc.stderr.decode(errors='replace').strip()}")
    print(f"  wrote {args.out}")

    # One page is the whole constraint, so it is worth failing loudly rather than quietly
    # shipping two. Counting /Type /Page while excluding the /Type /Pages tree node.
    blob = args.out.read_bytes()
    pages = blob.count(b"/Type /Page") - blob.count(b"/Type /Pages")
    print(f"  {pages} page(s), {len(blob) / 1024:.0f} kB")
    if pages != 1:
        sys.exit(f"  ERROR: the one-pager is {pages} pages — tighten it")


if __name__ == "__main__":
    main()
