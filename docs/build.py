#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["markdown"]
# ///
"""Render docs/METHOD.md into a single self-contained HTML page.

    ./docs/build.py                      # writes out/method.html
    ./docs/build.py --out /tmp/m.html

METHOD.md is the source of truth: it lives next to the code, so prose changes show up as line
diffs and GitHub renders it natively. This produces the *reading* view of the same text — a
sticky table of contents with scroll-spy, tabular figures in the tables, and both colour themes —
which 1,700 lines and two dozen tables need and Markdown cannot express.

No external assets: the CSS and JS are inlined and the type is a system font stack, so the output
works offline and inside a strict content-security policy.
"""

from __future__ import annotations

import argparse
import html
import re
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "METHOD.md"

# The header diagram: the document's own central finding, drawn. Five puzzles at their true
# spacing, and the same five as gated data reports them — compressed toward the middle by the
# slope the experiment measures.
COMPRESSION_SLOPE = 2.35


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
CSS = """
:root{
  --ground:#f7f8fa; --surface:#ffffff; --surface-2:#f1f3f7;
  --ink:#14181f; --ink-soft:#4d5666; --ink-faint:#7b8494;
  --rule:#dfe3ea; --rule-soft:#eaeef3;
  --ungated:#2563eb; --gated:#c2381f; --linking:#15803d;
  --accent:var(--ungated);
  --serif:Georgia,"Iowan Old Style","Palatino Linotype",Palatino,"Times New Roman",serif;
  --mono:ui-monospace,"SF Mono",SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace;
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --ground:#0f1319; --surface:#161c24; --surface-2:#1b222c;
    --ink:#e6eaf0; --ink-soft:#9aa5b5; --ink-faint:#75808f;
    --rule:#263040; --rule-soft:#1e2632;
    --ungated:#6ea8ff; --gated:#ff8a70; --linking:#5fcf8a;
  }
}
:root[data-theme="dark"]{
  --ground:#0f1319; --surface:#161c24; --surface-2:#1b222c;
  --ink:#e6eaf0; --ink-soft:#9aa5b5; --ink-faint:#75808f;
  --rule:#263040; --rule-soft:#1e2632;
  --ungated:#6ea8ff; --gated:#ff8a70; --linking:#5fcf8a;
}
*{box-sizing:border-box}
body{background:var(--ground);color:var(--ink);font-family:var(--serif);
  font-size:17px;line-height:1.68;margin:0;-webkit-font-smoothing:antialiased}
a{color:var(--accent);text-decoration-thickness:1px;text-underline-offset:2px}
a:focus-visible,summary:focus-visible{outline:2px solid var(--accent);outline-offset:3px;
  border-radius:2px}

.shell{max-width:1240px;margin:0 auto;padding:0 28px}
.layout{display:grid;grid-template-columns:250px minmax(0,1fr);gap:56px;align-items:start}
@media (max-width:1040px){.layout{grid-template-columns:minmax(0,1fr);gap:0}}

header.hero{border-bottom:1px solid var(--rule);margin-bottom:40px}
.hero-in{padding:56px 0 36px}
.eyebrow{font-family:var(--mono);font-size:11px;letter-spacing:.14em;text-transform:uppercase;
  color:var(--ink-faint);margin:0 0 18px}
h1{font-size:clamp(30px,4.4vw,46px);line-height:1.1;letter-spacing:-.02em;font-weight:700;
  margin:0;text-wrap:balance;max-width:22ch}
.lede{color:var(--ink-soft);max-width:66ch;margin:20px 0 0}
.lede p{margin:0 0 12px}
.lede strong{color:var(--ink)}
.motif{display:block;width:100%;max-width:660px;height:auto;margin:34px 0 4px;overflow:visible}
.motif .axis line{stroke:var(--rule);stroke-width:1}
.motif .tick-true line{stroke:var(--ungated);stroke-width:2.5;stroke-linecap:round}
.motif .tick-comp line{stroke:var(--gated);stroke-width:2.5;stroke-linecap:round}
.motif .join path{fill:none;stroke:var(--ink-faint);stroke-width:1;stroke-dasharray:2 3;opacity:.75}
.motif .lbl{font-family:var(--mono);font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;
  fill:var(--ink-faint)}
.motif .cap{font-family:var(--mono);font-size:11px;fill:var(--ink-soft)}
@media (max-width:720px){.motif .cap{display:none}}

nav.toc{position:sticky;top:0;max-height:100vh;overflow-y:auto;padding:8px 0 48px;
  font-family:var(--mono);font-size:12.5px;line-height:1.5}
nav.toc>h2{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-faint);
  margin:0 0 14px;font-weight:500;border:0;padding:0}
.toc-list,.toc-sub{list-style:none;margin:0;padding:0}
.toc-list{display:flex;flex-direction:column;gap:2px}
.toc-sec>a{display:grid;grid-template-columns:22px 1fr;gap:8px;padding:5px 8px 5px 0;
  text-decoration:none;color:var(--ink);border-radius:3px}
.toc-sec>a:hover{color:var(--accent)}
.toc-num{color:var(--ink-faint);font-variant-numeric:tabular-nums}
.toc-sub{margin:0 0 10px 30px;display:flex;flex-direction:column;gap:1px;
  border-left:1px solid var(--rule-soft);padding-left:12px}
.toc-sub a{display:block;padding:3px 0;color:var(--ink-soft);text-decoration:none;font-size:12px}
.toc-sub a:hover{color:var(--accent)}
nav.toc a.active{color:var(--accent)}
.toc-sec>a.active .toc-num{color:var(--accent)}
.toc-mobile{display:none}
@media (max-width:1040px){
  nav.toc{position:static;max-height:none;overflow:visible;border-bottom:1px solid var(--rule);
    margin-bottom:32px;padding-bottom:20px}
  .toc-mobile{display:block}
  nav.toc>h2{display:none}
  .toc-desktop{display:none}
  .toc-mobile summary{cursor:pointer;font-size:11px;letter-spacing:.14em;text-transform:uppercase;
    color:var(--ink-faint);padding:10px 0}
}

article{padding-bottom:96px;min-width:0}
article>*{max-width:68ch}
h2{font-size:clamp(23px,2.6vw,29px);line-height:1.2;letter-spacing:-.015em;font-weight:700;
  margin:72px 0 6px;padding-top:22px;border-top:1px solid var(--rule);text-wrap:balance}
h2:first-child{margin-top:0;border-top:0;padding-top:0}
h3{font-size:18.5px;line-height:1.3;font-weight:700;margin:38px 0 4px;letter-spacing:-.008em;
  text-wrap:balance;color:var(--ink)}
p{margin:14px 0}
ul,ol{margin:14px 0;padding-left:22px}
li{margin:7px 0}
li>p{margin:7px 0}
blockquote{margin:20px 0;padding:2px 0 2px 20px;border-left:2px solid var(--accent);
  color:var(--ink-soft);font-style:italic}
blockquote p{margin:6px 0}
hr{border:0;border-top:1px solid var(--rule);margin:44px 0}

code{font-family:var(--mono);font-size:.855em;background:var(--surface-2);padding:.12em .34em;
  border-radius:3px;color:var(--ink)}
pre{background:var(--surface);border:1px solid var(--rule);border-radius:5px;padding:16px 18px;
  overflow-x:auto;margin:20px 0;max-width:82ch;line-height:1.55}
pre code{background:none;padding:0;font-size:12.9px;white-space:pre}

.tw{overflow-x:auto;margin:22px 0;max-width:100%;border:1px solid var(--rule);border-radius:5px;
  background:var(--surface)}
table{border-collapse:collapse;width:100%;font-size:14px;font-family:var(--mono)}
th{font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;color:var(--ink-faint);
  font-weight:500;text-align:left;padding:11px 14px;border-bottom:1px solid var(--rule);
  white-space:nowrap;background:var(--surface-2)}
td{padding:9px 14px;border-bottom:1px solid var(--rule-soft);vertical-align:top;
  color:var(--ink-soft);line-height:1.5}
tr:last-child td{border-bottom:0}
td.num{font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap;color:var(--ink)}
td strong{color:var(--ink)}
td code,th code{font-size:12.5px;background:none;padding:0}
td:not(.num){font-family:var(--serif);font-size:15px}

.footer{border-top:1px solid var(--rule);padding:26px 0 60px;color:var(--ink-faint);
  font-family:var(--mono);font-size:12px;max-width:68ch}
@media (prefers-reduced-motion:no-preference){html{scroll-behavior:smooth}}
h2,h3{scroll-margin-top:18px}
"""

# Highlight the table-of-contents entry for whatever heading is currently at the top of the
# viewport. Worth the JS at this length; the page is perfectly usable without it.
JS = """
const links=[...document.querySelectorAll('nav.toc a')];
const map=new Map();
links.forEach(a=>{const k=a.getAttribute('href').slice(1);(map.get(k)||map.set(k,[]).get(k)).push(a)});
const seen=new Map();
const io=new IntersectionObserver(es=>{
  es.forEach(e=>seen.set(e.target.id,e));
  let best=null;
  for(const [,e] of seen){
    if(!e.isIntersecting) continue;
    if(!best||e.target.getBoundingClientRect().top<best.target.getBoundingClientRect().top) best=e;
  }
  if(!best) return;
  links.forEach(a=>a.classList.remove('active'));
  (map.get(best.target.id)||[]).forEach(a=>a.classList.add('active'));
},{rootMargin:'-8% 0px -70% 0px',threshold:0});
document.querySelectorAll('article h2, article h3').forEach(h=>{if(h.id) io.observe(h)});
"""


def build_nav(toc_tokens: list) -> str:
    out = ['<ol class="toc-list">']
    for t in toc_tokens:
        num, _, name = t["name"].partition(". ")
        out.append(
            f'<li class="toc-sec"><a href="#{t["id"]}">'
            f'<span class="toc-num">{html.escape(num)}</span>'
            f'<span class="toc-name">{html.escape(name or t["name"])}</span></a>'
        )
        if t["children"]:
            out.append('<ul class="toc-sub">')
            for c in t["children"]:
                out.append(f'<li><a href="#{c["id"]}">{html.escape(c["name"])}</a></li>')
            out.append("</ul>")
        out.append("</li>")
    out.append("</ol>")
    return "\n".join(out)


def mark_numeric_cells(body: str) -> str:
    """Tag purely numeric table cells so they can take the mono, right-aligned, tabular treatment."""

    def one(m: re.Match) -> str:
        attrs, inner = m.group(1), m.group(2)
        plain = re.sub(r"<[^>]+>", "", inner).strip()
        numeric = plain and re.fullmatch(r"[−–—\-+]?[\d.,]+\s*(×|x|%)?", plain)
        cls = ' class="num"' if numeric else ""
        return f"<td{cls}{attrs}>{inner}</td>"

    return re.sub(r"<td([^>]*)>(.*?)</td>", one, body, flags=re.S)


def render(md_text: str) -> str:
    # Split the h1 and its lede off the body so the hero can be composed explicitly.
    split = re.search(r"^## 1\. ", md_text, re.M)
    front, body_md = md_text[: split.start()], md_text[split.start() :]
    title = re.search(r"^# (.+)$", front, re.M).group(1)
    lede_md = "\n".join(
        line
        for line in front.splitlines()[1:]
        if line.strip() and not line.startswith("#") and not line.startswith("---")
    )

    md = markdown.Markdown(
        extensions=["tables", "fenced_code", "toc", "attr_list", "sane_lists"],
        extension_configs={"toc": {"toc_depth": "2-3", "permalink": False}},
    )
    body = md.convert(body_md)
    toc_tokens = md.toc_tokens  # capture before any reset() clears it
    lede = markdown.Markdown(extensions=["sane_lists"]).convert(lede_md)

    body = mark_numeric_cells(body)
    body = body.replace("<table>", '<div class="tw"><table>').replace("</table>", "</table></div>")
    nav = build_nav(toc_tokens)

    return f"""<title>Measuring Go Puzzle Difficulty</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>{CSS}</style>
<header class="hero"><div class="shell"><div class="hero-in">
  <p class="eyebrow">Method note &middot; gomagic-glicko</p>
  <h1>{html.escape(title)}</h1>
  <div class="lede">{lede}</div>
  {motif()}
</div></div></header>
<div class="shell"><div class="layout">
  <nav class="toc" aria-label="Contents">
    <h2>Contents</h2>
    <details class="toc-mobile"><summary>Contents</summary>{nav}</details>
    <div class="toc-desktop">{nav}</div>
  </nav>
  <article>{body}</article>
</div></div>
<div class="shell"><p class="footer">Every figure in this document is reproduced by a committed
command at seed 20260816. Public data and simulation only.</p></div>
<script>{JS}</script>
"""


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--out", type=Path, default=ROOT / "out" / "method.html")
    args = ap.parse_args()

    page = render(SRC.read_text())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(page)
    print(f"  wrote {args.out}  ({len(page):,} bytes)\n")


if __name__ == "__main__":
    main()
