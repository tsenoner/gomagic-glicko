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


def build_html(chart: str, css: str) -> str:
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
modelling Go Magic is skill-tree gating, where a player meets only puzzles near their own level. Fit Glicko-2 with the truth hidden, then score the fitted difficulties against it. Scale:
<strong>&plusmn;100 points &asymp; one Go rank</strong> (EGF convention, accurate at 1d and
generous below); assigning every puzzle the same difficulty scores 467.</p>

<div class="finding">
  <p class="lead">About 160 first attempts measure a puzzle's difficulty to roughly one rank,
  but on skill-tree data only if the log is fitted <em>jointly</em>. Replaying the same log
  one attempt at a time, the standard online way, leaves almost three ranks of error:
  <span class="num">287</span> points against <span class="num">112</span>, a
  <span class="num">61%</span> cut from how the fit is run alone.</p>
  <p class="note">The failure mode it avoids: reading 290 points of error off an online refit and
  concluding the data is inadequate.</p>
</div>

<div class="split">
  <figure>
    <img src="{chart}" alt="Difficulty recovery error against first attempts per puzzle">
    <figcaption><strong>Online Glicko-2 under three exposure patterns:</strong> ungated random
    pairing (a diagnostic test), skill-tree gating as implied by Go Magic's public tree, and gating
    with 10% of traffic ungated. Dotted line is one-rank accuracy; bands are 95% intervals over ten
    planted worlds.</figcaption>
    <p class="repro"><strong>Reproduce.</strong>
    <code>./src/recovery.py --puzzles 300 --reps 10</code> draws the curves;
    <code>./src/batch_fit.py</code> refits the identical log jointly. Every other number here is one
    command in <code>docs/RUNNING.md</code>; the estimator is checked against Glickman's worked
    example.</p>
  </figure>
  <div>
    <h2>Three results</h2>
    <div class="stack">
      <div>
        <h3>Gating itself costs accuracy</h3>
        <p>Under gating no attempt directly compares an easy puzzle with a hard one:
        <span class="num">1.6&times;</span> the error at 10 first attempts per puzzle,
        <span class="num">2.7&times;</span> at 160, and a smaller check holds ~2.8&times; out to
        1,280. Traffic does not close it.</p>
      </div>
      <div>
        <h3>The damage is to the spacing, not the ordering</h3>
        <p>At 160 attempts the fit still ranks puzzles well (Spearman
        <span class="num">0.94</span>), but compresses the scale to under half its width. It knows
        <em>which</em> puzzle is harder, not <em>by how much</em>. Compression is repairable.</p>
      </div>
      <div>
        <h3>Uneven traffic is a second, separate cost</h3>
        <p>Everybody attempts the first node; few reach the last. At matched volume that funnel
        costs <span class="num">30&ndash;50</span> points and drops the ordering from 0.94 to
        <span class="num">0.78</span>, the one thing gating had left intact.</p>
      </div>
    </div>
    <table class="mini">
      <thead><tr>
        <th>first attempts<br>per puzzle</th><th>ungated</th>
        <th>gated,<br>online</th><th>gated,<br>joint fit</th>
      </tr></thead>
      <tbody>
        <tr><td>10</td><td>250</td><td>408</td><td>388</td></tr>
        <tr><td>40</td><td>167</td><td>355</td><td>252</td></tr>
        <tr><td>160</td><td>107</td><td>287</td><td class="win">112</td></tr>
      </tbody>
    </table>
    <p class="tnote">RMSE in rating points, mean offset removed, since neither estimator fixes an
    origin (&plusmn;100 &asymp; one rank). Ten planted worlds; the last two columns fit the
    identical log, so only the estimator differs. 95% intervals &plusmn;3&ndash;8; every contrast
    significant.</p>
  </div>
</div>

<h2>What to do about it</h2>
<div class="cols">
  <div>
    <h3>Backfill jointly, serve online</h3>
    <p>Fit the history once, jointly, for the labels; keep online Glicko-2 for the live path, where
    one-at-a-time updating is right.</p>
  </div>
  <div>
    <h3>Ship labels per puzzle, not per catalogue</h3>
    <p>Coverage will never be uniform: publish a measured label only where the attempts exist.
    But not on Glicko's own RD, which under gating claims <span class="num">3.7&times;</span> more
    precision than it delivers.</p>
  </div>
  <div>
    <h3>Anchor the scale with an ungated test</h3>
    <p>An ungated diagnostic spanning the rank range is the standard repair for a compressed scale:
    25% of traffic through one buys back <span class="num">57</span> points and much of the
    compression.</p>
  </div>
</div>

<div class="caveat">
  <strong>What this does not claim.</strong> Not that any hand-assigned label is wrong; testing
  that needs the private attempt log. It answers the prior question: if difficulty were
  measured from attempts, how much data would the answer need to mean anything? That depends only
  on the estimator and the <em>shape</em> of the data, so simulation settles it, and nothing here
  uses private data.
  <br><br>
  <strong>The next step is small:</strong> run the joint fit over one month of the real log, first
  attempts only, and check the recovery curve against it.
</div>

<footer>
  <span>Tobias Senoner &middot; github.com/tsenoner/gomagic-glicko</span>
  <span>Method, derivations and sourcing: <code>docs/METHOD.md</code></span>
</footer>

</body></html>
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--chart", type=Path, default=ROOT / "out" / "recovery.png")
    ap.add_argument("--out", type=Path, default=ROOT / "out" / "onepager.pdf")
    ap.add_argument("--html-only", action="store_true")
    args = ap.parse_args()

    if not args.chart.exists():
        sys.exit(f"missing {args.chart} — run ./src/recovery.py --puzzles 300 --reps 10 first")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    html_path = args.out.with_suffix(".html")
    html_path.write_text(build_html(data_uri(args.chart), read_css()))
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
