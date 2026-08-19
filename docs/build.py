#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["markdown>=3.4"]
# ///
"""Render docs/METHOD.md into a single self-contained HTML page.

    ./docs/build.py                      # writes out/method.html
    ./docs/build.py --out /tmp/m.html

METHOD.md is the source of truth: it lives next to the code, so prose changes show up as line
diffs and GitHub renders it natively. This produces the *reading* view of the same text — a
collapsing table of contents with scroll-spy, hoverable citations, and both colour themes — which
1,800 lines, two dozen tables and nine cited sources need and Markdown cannot express.

No external assets: the CSS and JS are inlined and the type is a system font stack, so the output
works offline, inside a strict content-security policy, and inside a sandboxed iframe.

Three constraints that shaped the JS, all of them measured rather than assumed:

  * Native fragment navigation already restores the exact pre-jump scroll position, in every
    engine, including in a sandboxed iframe. So the back/forward control is a *labelled wrapper*
    around history.back() — it does not reimplement scroll memory, and never touches
    history.scrollRestoration, which measurably leaves the reader at the jump target instead.
  * The iframe shares the host's session history, so history.back() at depth 0 would navigate the
    host away. Every traversal is gated on a depth derived from stamped history.state.
  * sessionStorage and localStorage throw SecurityError here (on property access, so even
    `if (window.localStorage)` throws). Nothing persists across reload except history.state.
"""

from __future__ import annotations

import argparse
import html
import re
import shutil
import subprocess
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "METHOD.md"

# The stylesheet and the script live as real files, not as Python strings. They are pure static
# assets — nothing is interpolated into them — and as strings no editor highlighted them, no linter
# read them, and a syntax error inside one was invisible until it silently disabled the page at
# runtime. As files they are checked directly, by the tools that understand them.
ASSETS = ROOT / "docs" / "assets"
STYLE = ASSETS / "style.css"
APP = ASSETS / "app.js"

# The header diagram: the document's own central finding, drawn. Five puzzles at their true
# spacing, and the same five as gated data reports them — compressed toward the middle by the
# slope the experiment measures.
COMPRESSION_SLOPE = 2.36


def motif(width: int = 660, left: int = 96, span: int = 520) -> str:
    mid = left + span / 2
    rows = []
    for k in range(5):
        x = left + span * k / 4
        rows.append((x, mid + (x - mid) / COMPRESSION_SLOPE))
    ticks_true = "".join(f'<line x1="{x:.1f}" y1="34" x2="{x:.1f}" y2="52" />' for x, _ in rows)
    ticks_comp = "".join(f'<line x1="{c:.1f}" y1="96" x2="{c:.1f}" y2="114" />' for _, c in rows)
    joins = "".join(
        f'<path d="M {x:.1f} 52 C {x:.1f} 74, {c:.1f} 74, {c:.1f} 96" />' for x, c in rows
    )
    return f"""<svg class="motif" viewBox="0 0 {width} 150" role="img"
     aria-label="Two measurement scales: five puzzles at their true spacing above, and the same
     five compressed {COMPRESSION_SLOPE} times toward the middle below, which is what gated data
     produces.">
  <g class="axis"><line x1="{left}" y1="43" x2="{left + span}" y2="43" />
                  <line x1="{left}" y1="105" x2="{left + span}" y2="105" /></g>
  <g class="tick-true">{ticks_true}</g>
  <g class="join">{joins}</g>
  <g class="tick-comp">{ticks_comp}</g>
  <text class="lbl" x="{left - 14}" y="47" text-anchor="end">true</text>
  <text class="lbl" x="{left - 14}" y="109" text-anchor="end">measured</text>
  <text class="cap" x="{left + span + 14}" y="47">the spread that exists</text>
  <text class="cap" x="{left + span + 14}" y="109">what gating reports (slope {COMPRESSION_SLOPE})</text>
</svg>"""


# Palette taken from the repo's own plot (src/recovery.py): blue is the ungated regime, red the
# gated one, green the linking items. The reds are deepened from the plot values so they hold up
# as text. Every token is defined on bare :root first, then redefined for dark — a colour whose
# only definition sits behind a media query never applies in the viewer's default "system" state.


def build_nav(toc_tokens: list) -> str:
    """One nav, rendered once. Two copies would put aria-current on two links for the same id."""
    out = ['<ol class="toc-list" id="toc-sections">']
    for t in toc_tokens:
        num, _, name = t["name"].partition(". ")
        name = name or t["name"]
        kids = t["children"]
        gid = "toc-g" + re.sub(r"\W+", "", num or t["id"])
        out.append('<li class="toc-sec">')
        out.append(
            f'<a href="#{t["id"]}">'
            f'<span class="toc-num">{html.escape(num)}</span>'
            f'<span class="toc-name">{html.escape(name)}</span>'
            + (f'<span class="toc-count" aria-hidden="true">{len(kids)}</span>' if kids else "")
            + "</a>"
        )
        if kids:
            # A section-naming label, because eight buttons all called "Toggle" are
            # indistinguishable in a screen reader's element list.
            lbl = html.escape(f"Subsections of section {num}, {name} ({len(kids)} items)")
            out.append(
                f'<button class="twist" type="button" aria-expanded="false" '
                f'aria-controls="{gid}" aria-label="{lbl}">'
                f'<svg aria-hidden="true" viewBox="0 0 10 10"><path d="M3 2l4 3-4 3z"/></svg>'
                f"</button>"
            )
            out.append(f'<ul class="toc-sub" id="{gid}">')
            for c in kids:
                out.append(f'<li><a href="#{c["id"]}">{html.escape(c["name"])}</a></li>')
            out.append("</ul>")
        out.append("</li>")
    out.append("</ol>")
    return "\n".join(out)


NUMERIC = re.compile(r"[+\u2212-]?[\d.,]+(?:\s*[\u2013\u2014-]\s*[\d.,]+)?\s*(?:[\u00d7x%]|px)?\Z")


def _plain(cell_html: str) -> str:
    return re.sub(r"<[^>]+>", "", cell_html).strip()


def align_table_columns(body: str) -> str:
    """Right-align numeric columns, and keep short label cells on one line.

    Alignment is decided per COLUMN, never per cell. Deciding it per cell meant one odd value
    broke the column it lived in: a "Glickman's step" column reading 1-2, 3, 4 ... 8 rendered its
    first cell left-aligned in the serif (the en dash is not a digit) and the rest right-aligned in
    the mono, so the column visibly staggered. A column is numeric only if *every* populated cell
    in it is, and then the header goes with it.

    Short first-column cells also get `nowrap`, because a table whose later columns hold long prose
    squeezes the label column until words break at their hyphens -- "Glicko-2" rendering as
    "Glicko-" over "2".
    """

    def one_table(tm: re.Match) -> str:
        table = tm.group(0)
        rows = re.findall(r"<tr>(.*?)</tr>", table, re.S)
        body_cols: list[list[str]] = []
        for row in rows:
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
            for i, c in enumerate(cells):
                while len(body_cols) <= i:
                    body_cols.append([])
                body_cols[i].append(_plain(c))

        numeric_col = [
            bool(col) and all(NUMERIC.fullmatch(v) for v in col if v) and any(col)
            for col in body_cols
        ]
        # A label column is the first one when it is not numeric and every entry is short enough
        # that nowrap cannot push the table wide.
        label_col0 = (
            bool(body_cols)
            and not numeric_col[0]
            and all(len(v) <= 16 for v in body_cols[0])
        )

        def retag(row_html: str, tag: str) -> str:
            idx = [0]

            def cell(m: re.Match) -> str:
                i = idx[0]
                idx[0] += 1
                attrs, inner = m.group(1), m.group(2)
                classes = []
                if i < len(numeric_col) and numeric_col[i]:
                    classes.append("num")
                elif i == 0 and label_col0:
                    classes.append("lbl")
                cls = f' class="{" ".join(classes)}"' if classes else ""
                return f"<{tag}{cls}{attrs}>{inner}</{tag}>"

            return re.sub(rf"<{tag}([^>]*)>(.*?)</{tag}>", cell, row_html, flags=re.S)

        return re.sub(
            r"<tr>(.*?)</tr>",
            lambda rm: "<tr>" + retag(retag(rm.group(1), "td"), "th") + "</tr>",
            table,
            flags=re.S,
        )

    return re.sub(r"<table>.*?</table>", one_table, body, flags=re.S)


REF_DIV = re.compile(r'\n?<div class="footnote">\s*<hr\s*/?>\s*(<ol>.*?</ol>)\s*</div>', re.S)


def transform_refs(body: str) -> str:
    """Re-class python-markdown's footnote output into a proper DPUB-ARIA reference list.

    role="doc-endnotes" goes on a wrapper div, never on the <ol> — a landmark role there strips
    list semantics and the "3 of 9" position announcement.
    """
    m = REF_DIV.search(body)
    if m:
        refs = m.group(1)
        refs = refs.replace("<ol>", '<ol class="ref-list">', 1)
        refs = refs.replace('<li id="fn-', '<li role="doc-footnote" id="fn-')
        refs = refs.replace("&#160;<a class=\"footnote-backref\"", ' <a class="footnote-backref"')

        # Number the entries in document order, then label each backref per instance. The stock
        # title="Jump back to footnote 1 in the text" is identical on every repeat backref, and
        # title is unreachable by keyboard and invisible on touch.
        counter = {"n": 0}

        def one_li(li: re.Match) -> str:
            counter["n"] += 1
            num = counter["n"]
            seen = {"k": 0}

            def one_a(a: re.Match) -> str:
                seen["k"] += 1
                k = seen["k"]
                lbl = f"Back to reference {num}" if k == 1 else f"Back to reference {num}-{k}"
                tail = "" if k == 1 else f"<sup>{chr(96 + k)}</sup>"
                # U+FE0E forces text presentation: bare U+21A9 renders as a colour emoji on some
                # mobile font stacks, which looks broken in a page set in Georgia.
                return (
                    f'<a class="footnote-backref" role="doc-backlink" aria-label="{lbl}"'
                    f'{a.group(1)}>&#8617;&#xFE0E;{tail}</a>'
                )

            return re.sub(
                r'<a class="footnote-backref"[^>]*?(\shref="[^"]+")[^>]*>(?:&#8617;|↩)\s*</a>',
                one_a,
                li.group(0),
            )

        refs = re.sub(r"<li role=\"doc-footnote\".*?</li>", one_li, refs, flags=re.S)
        body = body[: m.start()] + f'<div role="doc-endnotes">{refs}</div>' + body[m.end():]

    # Markers: add the role and the key the popover reads.
    return re.sub(
        r'<sup id="fnref([\d]*)-([^"]+)"><a class="footnote-ref" href="#fn-([^"]+)">(\d+)</a></sup>',
        lambda a: (
            f'<sup><a class="cite-ref" role="doc-noteref" id="fnref{a.group(1)}-{a.group(2)}"'
            f' data-fnkey="{a.group(3)}" href="#fn-{a.group(3)}">{a.group(4)}</a></sup>'
        ),
        body,
    )


def check_ref_order(body: str) -> None:
    """Fail if the [^key]: definitions are not in first-reference order.

    python-markdown numbers footnotes by DEFINITION order; GitHub numbers them by FIRST REFERENCE.
    When those disagree the same source renders as note 9 here and note 1 there, so the two
    renderings of one document cite different numbers.

    Read from the parser's own output rather than from the Markdown. The previous version regexed
    the raw source and had to strip fenced blocks and code spans itself so that regex literals like
    `[^>]+` in this document were not mistaken for citations — a second, approximate copy of
    Markdown's code-span rules that handled ``` and single backticks but not indented blocks, `~~~`
    fences or double-backtick spans. Any of those containing a [^x] token failed the build with a
    demand to reorder definitions that were already correct.
    """
    first = list(dict.fromkeys(re.findall(r'id="fnref\d*-([^"]+)"', body)))
    defs = re.findall(r'<li[^>]*\bid="fn-([^"]+)"', body)
    if defs != first:
        raise SystemExit(
            "docs/METHOD.md: reorder the [^key]: definitions to first-reference order:\n  "
            + ", ".join(first)
        )


def render(md_text: str, css: str, js: str) -> str:
    # Split the h1 and its lede off the body so the hero can be composed explicitly.
    split = re.search(r"^## 1\. ", md_text, re.M)
    front, body_md = md_text[: split.start()], md_text[split.start():]
    # The lede is converted by a second Markdown instance with no footnotes extension, so a marker
    # up there would ship as raw text in the hero.
    if "[^" in front:
        raise SystemExit("docs/METHOD.md: citations are not supported above '## 1.' (the lede)")

    title = re.search(r"^# (.+)$", front, re.M).group(1)
    # Keep blank lines: they are the paragraph breaks. Filtering them merged the lede's two
    # paragraphs into one, so the reading view did not match the source it mirrors.
    lede_md = "\n".join(
        line
        for line in front.splitlines()[1:]
        if not line.startswith("#") and not line.startswith("---")
    ).strip()

    md = markdown.Markdown(
        extensions=["tables", "fenced_code", "toc", "attr_list", "sane_lists", "footnotes"],
        extension_configs={
            "toc": {"toc_depth": "2-3", "permalink": False},
            # "-" keeps ids as fn-key / fnref-key rather than colon-separated.
            "footnotes": {"SEPARATOR": "-"},
        },
    )
    body = md.convert(body_md)
    check_ref_order(body)
    toc_tokens = md.toc_tokens  # capture before any reset() clears it
    lede = markdown.Markdown(extensions=["sane_lists"]).convert(lede_md)

    body = align_table_columns(body)
    body = transform_refs(body)
    body = body.replace("<table>", '<div class="tw"><table>').replace("</table>", "</table></div>")
    nav = build_nav(toc_tokens)

    # charset first: the HTML encoding prescan only looks at the first 1024 bytes, and without it
    # a standalone `out/method.html` is decoded as Latin-1 — every em dash becomes "â€”" and the
    # backref arrows turn to mojibake. Harmless when a publishing wrapper supplies its own head.
    return f"""<meta charset="utf-8">
<title>Measuring Go Puzzle Difficulty</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
{css}</style>
<header class="hero" id="top"><div class="shell"><div class="hero-in">
  <p class="eyebrow">Method note &middot; gomagic-glicko</p>
  <h1>{html.escape(title)}</h1>
  <div class="lede">{lede}</div>
  {motif()}
</div></div></header>
<div class="shell"><div class="layout">
  <nav class="toc" aria-label="Contents">
    <div class="toc-bar">
      <button id="tocbtn" type="button" aria-expanded="false" aria-controls="toc-sections">
        <span class="toc-num" id="tocbtn-num">1</span>
        <span id="tocbtn-label">Introduction</span>
        <span class="caret" aria-hidden="true">&#9662;</span>
      </button>
    </div>
    <a class="toc-top" href="#top">Contents</a>
    <label class="toc-find"><span class="sr-only">Filter contents</span>
      <input id="tocq" type="search" autocomplete="off" spellcheck="false"
             placeholder="Filter&hellip;  (press /)"></label>
    <p id="tocq-n" role="status" class="sr-only"></p>
    {nav}
  </nav>
  <article>{body}</article>
</div></div>
<div class="shell"><p class="footer">Every figure in this document is reproduced by a committed
command at seed 20260816. Public data and simulation only.</p></div>
<div id="cite-pop" popover role="note" aria-label="Reference"></div>
<div class="jump" role="group" aria-label="Jump history" hidden>
  <button id="jump-back" type="button">
    <span class="arrow" aria-hidden="true">&larr;</span><span class="lbl" id="jump-label">Back</span>
  </button>
  <span class="sep" aria-hidden="true"></span>
  <button id="jump-fwd" type="button" aria-label="Forward again" hidden>
    <span class="arrow" aria-hidden="true">&rarr;</span>
  </button>
  <span class="sep" aria-hidden="true"></span>
  <button class="close" id="jump-close" type="button" aria-label="Dismiss the jump history bar">
    <span aria-hidden="true">&times;</span>
  </button>
</div>
<p id="jump-status" role="status" aria-live="polite" class="sr-only"></p>
<script>
{js}</script>
"""


def check_css(path: Path) -> str:
    """Cheap structural check on the stylesheet: are the braces balanced?

    A stray closing brace does not stop a browser — it recovers and drops one rule — so an
    unbalanced stylesheet ships looking almost right. One did: the dark palette was briefly
    templated through Python and left an extra `}` behind.
    """
    css = path.read_text()
    stripped = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    opens, closes = stripped.count("{"), stripped.count("}")
    if opens != closes:
        raise SystemExit(f"{path.name}: unbalanced braces — {opens} open, {closes} close")
    return css


def check_js(path: Path) -> str:
    """Reject a script that would not parse, before it can ship.

    A parse-time SyntaxError anywhere in this script kills *all* of it, so the page degrades to a
    fully-expanded rail with no scroll-spy, no citation popover and no back control — and it still
    screenshots perfectly. That is exactly how the combining-marks regex shipped once.

    Two checks, in this order on purpose: the pure-Python one first, because it needs no engine and
    therefore is the only protection left on a machine that has none.
    """
    js = path.read_text()
    # A raw non-ASCII character inside a character class is how /[\u0300-\u036f]/ became the
    # invalid range /[Ì€-Í¯]/ after a re-encode. Em dashes in comments are fine; this is narrow.
    for cls in re.findall(r"\[(?:[^\]\\\n]|\\.)*\]", js):
        bad = [c for c in cls if not c.isascii()]
        if bad:
            raise SystemExit(
                f"{path.name}: non-ASCII character(s) {bad!r} inside the character class {cls!r}. "
                "Write them as \\uXXXX escapes — a re-encode turns them into an invalid range, "
                "which is a parse-time error that silently disables the whole script."
            )

    # node parses with --check. bun does NOT: it ignores the unknown flag and *executes* the file,
    # so `bun --check` on this script would run it headless and fail on a missing DOM, reporting a
    # syntax error that is not there. `bun build --no-bundle` parses without executing.
    # Checked in place: the file that ships is the file that is parsed, so there is no copy for
    # the check to drift away from.
    for exe, args in (("node", ["--check"]), ("bun", ["build", "--no-bundle"])):
        found = shutil.which(exe)
        if not found:
            continue
        r = subprocess.run([found, *args, str(path)], capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit(f"{path.name} failed to parse ({exe}):\n" + (r.stderr or r.stdout))
        return js

    print(f"  (no node or bun on PATH — character-class guard only on {path.name})")
    return js


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--out", type=Path, default=ROOT / "out" / "method.html")
    args = ap.parse_args()

    css = check_css(STYLE)
    js = check_js(APP)
    page = render(SRC.read_text(), css, js)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(page)
    print(f"  wrote {args.out}  ({len(page):,} bytes)\n")


if __name__ == "__main__":
    main()
