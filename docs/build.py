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
import os
import re
import shutil
import subprocess
import tempfile
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
  /* One property drives both where an anchored heading lands and where the scroll-spy probes,
     so clicking a rail link cannot highlight the row above the one you clicked. */
  --read-line:96px;
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
a:focus-visible,summary:focus-visible,button:focus-visible,input:focus-visible{
  outline:2px solid var(--accent);outline-offset:3px;border-radius:2px}
.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;
  clip-path:inset(50%);white-space:nowrap;border:0}
/* NOTE: no html{scroll-behavior:smooth}. It animated history restoration (Back visibly crawled
   back through 1,800 lines), it animated every citation jump, and it never reached the rail
   because scroll-behavior does not inherit. Rail scrolling asks for smooth explicitly in JS. */
h2,h3{scroll-margin-top:var(--read-line)}

.shell{max-width:1240px;margin:0 auto;padding:0 28px}
/* align-items:start is the only reason position:sticky works on the rail — grid's default
   stretch would size it to the article's full height, leaving nothing to stick. */
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

/* ---------------------------------------------------------------- the rail */
nav.toc{
  position:sticky; top:0;
  align-self:start;          /* required for sticky; see .layout above */
  max-height:100dvh;
  overflow-x:hidden;         /* overflow-y then computes to auto. Declaring overflow-y:auto with
                                overflow-x:visible makes overflow-x compute to auto too, which
                                gives a spurious horizontal scrollbar AND clips focus rings. */
  overscroll-behavior:contain;
  scrollbar-gutter:stable;
  padding:8px 10px 48px;     /* room for outline-offset:3px inside the scrollport */
  margin-inline:-10px;       /* pay that padding back to the grid */
  font-family:var(--mono); font-size:12.5px; line-height:1.5;
}
.toc-top{display:block;font-size:11px;letter-spacing:.14em;text-transform:uppercase;
  color:var(--ink-faint);margin:0 0 12px;text-decoration:none}
.toc-top:hover{color:var(--accent)}
.toc-find{display:block;margin:0 0 12px}
.toc-find input{width:100%;font:inherit;font-size:12px;color:var(--ink);
  background:var(--surface);border:1px solid var(--rule);border-radius:4px;padding:5px 8px}
.toc-find input::placeholder{color:var(--ink-faint)}
.toc-list,.toc-sub{list-style:none;margin:0;padding:0}
.toc-list{display:flex;flex-direction:column;gap:1px}
.toc-sec{position:relative}
.toc-sec>a{display:grid;grid-template-columns:22px 1fr auto;gap:8px;align-items:baseline;
  padding:5px 26px 5px 6px;text-decoration:none;color:var(--ink);border-radius:3px}
.toc-sec>a:hover{color:var(--accent);background:var(--surface-2)}
.toc-num{color:var(--ink-faint);font-variant-numeric:tabular-nums}
.toc-count{color:var(--ink-faint);font-variant-numeric:tabular-nums;font-size:11px}
.toc-sec[data-open] .toc-count{opacity:0}
.twist{position:absolute;top:2px;right:0;width:24px;height:24px;display:grid;place-items:center;
  background:none;border:0;padding:0;cursor:pointer;color:var(--ink-faint);border-radius:3px}
.twist:hover{color:var(--accent);background:var(--surface-2)}
.twist svg{width:9px;height:9px;fill:currentColor;transition:transform .15s ease}
@media (prefers-reduced-motion:reduce){.twist svg{transition:none}}
.toc-sec[data-open] .twist svg{transform:rotate(90deg)}
.toc-sub{margin:1px 0 8px 30px;display:flex;flex-direction:column;gap:1px;
  border-left:1px solid var(--rule-soft);padding-left:12px}
.toc-sub a{display:block;padding:3px 6px 3px 0;color:var(--ink-soft);text-decoration:none;
  font-size:12px;border-radius:3px}
.toc-sub a:hover{color:var(--accent)}
/* Collapsed only once JS says so, so the no-JS page ships fully expanded. */
nav.toc[data-js] .toc-sub{display:none}
nav.toc[data-js] .toc-sec[data-open]>.toc-sub{display:block}
.toc-sec[data-inside]>a{font-weight:700}
.toc-sec[data-inside]>a .toc-num{color:var(--accent)}
/* aria-current is the ONLY active-state hook: the visual state cannot drift from the announced
   one because there is no second variable. A static inset shadow, not an animated marker. */
nav.toc a[aria-current]{color:var(--accent);box-shadow:inset 2px 0 0 var(--accent)}
.toc-sec>a[aria-current] .toc-num{color:var(--accent)}
/* filter: these follow the accordion rules deliberately — equal specificity, later wins */
nav.toc.filtering li{display:none}
nav.toc.filtering li:has(a.hit){display:block}
nav.toc.filtering .toc-sub{display:block}
nav.toc.filtering .twist{visibility:hidden}
.toc-bar{display:none}

@media (max-width:1040px){
  nav.toc{position:sticky;top:0;max-height:none;overflow:visible;padding:0 0 16px;
    margin-inline:0;background:var(--ground);z-index:5;
    border-bottom:1px solid var(--rule);margin-bottom:32px}
  .toc-bar{display:block;position:sticky;top:0;background:var(--ground);
    border-bottom:1px solid var(--rule-soft)}
  .toc-bar button{display:flex;gap:10px;align-items:baseline;width:100%;text-align:left;
    font:inherit;color:var(--ink);background:none;border:0;padding:11px 2px;cursor:pointer}
  .toc-bar .caret{margin-left:auto;color:var(--ink-faint)}
  .toc-top{display:none}
  nav.toc[data-panel="closed"] .toc-list,
  nav.toc[data-panel="closed"] .toc-find{display:none}
  nav.toc .toc-list{max-height:70dvh;overflow-y:auto;overscroll-behavior:contain;padding-top:10px}
  :root{--read-line:calc(var(--toc-bar,44px) + 60px)}
}

/* ------------------------------------------------------------- the article */
article{padding-bottom:120px;min-width:0}
article>*{max-width:68ch}
h2{font-size:clamp(23px,2.6vw,29px);line-height:1.2;letter-spacing:-.015em;font-weight:700;
  margin:72px 0 6px;padding-top:22px;border-top:1px solid var(--rule);text-wrap:balance}
h2:first-child{margin-top:0;border-top:0;padding-top:0}
h3{font-size:18.5px;line-height:1.3;font-weight:700;margin:38px 0 4px;letter-spacing:-.008em;
  text-wrap:balance;color:var(--ink)}
h2:focus-visible,h3:focus-visible{outline:2px solid var(--accent);outline-offset:6px}
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

/* ----------------------------------------------------------- citations */
/* line-height:0 is load-bearing: an unstyled superscript inflates its line box, so every
   paragraph carrying a citation would sit visibly taller than its neighbours at 17px/1.68. */
sup{line-height:0;font-size:.72em;vertical-align:super;unicode-bidi:isolate}
.cite-ref{font-family:var(--mono);font-variant-numeric:tabular-nums;text-decoration:none;
  color:var(--accent);padding:.35em .3em;margin:-.35em -.1em;border-radius:3px}
/* brackets as generated content: the document is full of real exponents (σ², φ²) */
.cite-ref::before{content:"["}
.cite-ref::after{content:"]"}
.cite-ref:hover{background:var(--surface-2)}
.cite-ref:target{background:var(--surface-2);box-shadow:0 0 0 2px var(--accent)}
.footnote-backref{text-decoration:none;color:var(--ink-faint);padding:.2em .3em;margin-left:.15em}
.footnote-backref:hover{color:var(--accent)}
.footnote-backref sup{font-family:var(--mono);font-size:.7em}
.ref-list{font-size:15.5px;padding-left:26px}
.ref-list li{scroll-margin-top:var(--read-line);padding:4px 10px;margin-left:-10px;
  border-radius:4px}
.ref-list li p{margin:4px 0}
.ref-list code{font-size:.82em}
@media (prefers-reduced-motion:no-preference){.ref-list li{transition:background-color .3s ease}}
.ref-list li:target{background:var(--surface-2);box-shadow:inset 3px 0 0 var(--accent)}
#cite-pop{position:fixed;inset:auto;margin:0;width:max-content;
  max-width:min(46ch,calc(100vw - 24px));background:var(--surface);color:var(--ink);
  border:1px solid var(--rule);border-radius:6px;padding:12px 14px;font-family:var(--serif);
  font-size:14.5px;line-height:1.5;box-shadow:0 6px 24px rgb(0 0 0 / .18)}
#cite-pop:not(:popover-open){display:none}
#cite-pop p{margin:0}
#cite-pop code{font-size:.82em}

/* ------------------------------------------------------- back / forward */
.jump{position:fixed;left:50%;transform:translateX(-50%);bottom:20px;z-index:40;
  display:flex;align-items:stretch;gap:1px;background:var(--surface);
  border:1px solid var(--rule);border-radius:999px;overflow:hidden;
  box-shadow:0 4px 20px rgb(0 0 0 / .16);font-family:var(--mono);font-size:12.5px}
.jump[hidden]{display:none}
.jump button{font:inherit;color:var(--ink);background:none;border:0;cursor:pointer;
  padding:9px 15px;display:flex;align-items:center;gap:7px;max-width:34ch}
.jump button:hover{background:var(--surface-2);color:var(--accent)}
.jump button[hidden]{display:none}
.jump .lbl{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.jump .arrow{color:var(--ink-faint);flex:none}
.jump .sep{width:1px;background:var(--rule);flex:none}
@media (max-width:1040px){
  .jump{left:0;right:0;bottom:0;transform:none;border-radius:0;border-left:0;border-right:0;
    border-bottom:0;padding-bottom:env(safe-area-inset-bottom)}
  .jump button{flex:1;justify-content:center}
}

.footer{border-top:1px solid var(--rule);padding:26px 0 60px;color:var(--ink-faint);
  font-family:var(--mono);font-size:12px;max-width:68ch}
"""

JS = r"""
(function(){
'use strict';
var nav = document.querySelector('nav.toc');
var article = document.querySelector('article');
if (!nav || !article) return;

var reduce = matchMedia('(prefers-reduced-motion: reduce)');
var heads = [].slice.call(article.querySelectorAll('h2[id],h3[id]'));
var links = [].slice.call(nav.querySelectorAll('.toc-list a'));
var secs  = [].slice.call(nav.querySelectorAll('.toc-sec'));

/* ---------------------------------------------------------------- scroll-spy
   Cached offsets + binary search, not IntersectionObserver. A band-based observer has three
   reachable bugs on this document: sections run 200-600 lines so the band often contains no
   heading and the highlight freezes on a stale row; scrolling up fast the last intersection can
   belong to a heading below the reader; and the final h3 sits too near the document end to ever
   enter the band, so it is never highlightable. This scan is total, direction-independent and
   clamped at the tail. */
var tops = [], cur = -1, queued = false;
function LINE(){
  var v = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--read-line'));
  return (isNaN(v) ? 96 : v) + 24;
}
function measure(){
  tops = heads.map(function(h){ return h.getBoundingClientRect().top + scrollY; });
}
function pick(){
  queued = false;
  var doc = document.documentElement;
  if (scrollY + innerHeight >= doc.scrollHeight - 2) return set(heads.length - 1);
  var y = scrollY + LINE(), lo = 0, hi = tops.length - 1, i = 0;
  while (lo <= hi){ var m = (lo + hi) >> 1; if (tops[m] <= y){ i = m; lo = m + 1; } else hi = m - 1; }
  set(i);
}
function set(i){ if (i === cur || i < 0) return; cur = i; applyActive(heads[i]); }

function applyActive(h){
  var prev = nav.querySelector('a[aria-current]');
  if (prev) prev.removeAttribute('aria-current');
  var a = nav.querySelector('a[href="#' + (window.CSS && CSS.escape ? CSS.escape(h.id) : h.id) + '"]');
  if (!a) return;
  a.setAttribute('aria-current', 'location');
  var li = a.closest('.toc-sec');
  openGroup(li);
  reveal(a);
  syncBar(li);
}

/* --------------------------------------------------------------- accordion */
function openGroup(li){
  for (var i = 0; i < secs.length; i++){
    var s = secs[i];
    if (s === li){ s.setAttribute('data-open',''); s.setAttribute('data-inside',''); }
    else {
      s.removeAttribute('data-inside');
      if (!s.hasAttribute('data-pinned')) s.removeAttribute('data-open');
    }
    var b = s.querySelector('.twist');
    if (b) b.setAttribute('aria-expanded', s.hasAttribute('data-open') ? 'true' : 'false');
  }
}
nav.addEventListener('click', function(e){
  var t = e.target.closest('.twist');
  if (t){
    e.preventDefault();
    var li = t.closest('.toc-sec');
    if (li.hasAttribute('data-open')){ li.removeAttribute('data-open'); li.removeAttribute('data-pinned'); }
    else { li.setAttribute('data-open',''); li.setAttribute('data-pinned',''); }
    t.setAttribute('aria-expanded', li.hasAttribute('data-open') ? 'true' : 'false');
    return;
  }
  if (e.target.closest('.toc-list a')){
    for (var i = 0; i < secs.length; i++) secs[i].removeAttribute('data-pinned');
  }
});

/* Rail-local scrolling only. scrollIntoView() scrolls every scroll ancestor including the
   viewport, and container:'nearest' is Chrome-only — a rail nudge would drag the article out
   from under Firefox and Safari readers. */
function reveal(el){
  var pad = 56, r = el.getBoundingClientRect(), b = nav.getBoundingClientRect(), d = 0;
  if (r.top < b.top + pad) d = r.top - b.top - pad;
  else if (r.bottom > b.bottom - pad) d = r.bottom - b.bottom + pad;
  if (!d || nav.scrollHeight <= nav.clientHeight + 1) return;
  nav.scrollTo({ top: nav.scrollTop + d, behavior: reduce.matches ? 'auto' : 'smooth' });
}

/* ------------------------------------------------------------- mobile bar */
var bar = document.querySelector('.toc-bar');
var barBtn = document.getElementById('tocbtn');
var barNum = document.getElementById('tocbtn-num');
var barLbl = document.getElementById('tocbtn-label');
function syncBar(li){
  if (!barLbl || !li) return;
  var n = li.querySelector('.toc-num'), t = li.querySelector('.toc-name');
  if (n) barNum.textContent = n.textContent;
  if (t) barLbl.textContent = t.textContent;
}
if (barBtn){
  barBtn.addEventListener('click', function(){
    var open = nav.dataset.panel !== 'closed';
    nav.dataset.panel = open ? 'closed' : 'open';
    barBtn.setAttribute('aria-expanded', open ? 'false' : 'true');
  });
  nav.querySelector('.toc-list').addEventListener('click', function(e){
    if (e.target.closest('a') && nav.dataset.panel === 'open') barBtn.click();
  });
}
function barHeight(){
  if (bar) document.documentElement.style.setProperty('--toc-bar', bar.offsetHeight + 'px');
}

/* ---------------------------------------------------------------- filter */
var q = document.getElementById('tocq'), qn = document.getElementById('tocq-n');
function norm(s){
  /* U+0300-U+036F written as escapes, never as literal combining marks. Written literally
     they sit in the source as raw UTF-8 bytes that a re-encode can reinterpret as
     Latin-1, turning the range endpoints into the wrong code points and making the class
     an out-of-order range. That is a parse-time SyntaxError, which silently disables this
     entire script. docs/build.py check_js() now fails the build on it. */
  return s.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/\s+/g,' ');
}
if (q){
  q.addEventListener('input', function(){
    var s = norm(q.value.trim()), n = 0;
    nav.classList.toggle('filtering', !!s);
    for (var i = 0; i < links.length; i++){
      var hit = !!s && norm(links[i].textContent).indexOf(s) !== -1;
      links[i].classList.toggle('hit', hit);
      if (hit) n++;
    }
    qn.textContent = s ? (n + ' of ' + links.length + ' sections match') : '';
  });
  q.addEventListener('keydown', function(e){
    if (e.key === 'Enter'){
      e.preventDefault();
      var h = nav.querySelector('a.hit'); if (h) h.click();
    } else if (e.key === 'Escape'){
      q.value = ''; q.dispatchEvent(new Event('input'));
    }
  });
}
addEventListener('keydown', function(e){
  var t = e.target;
  if (!t || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName) || t.isContentEditable) return;
  if (e.altKey || e.ctrlKey || e.metaKey) return;
  if (e.key === '/' && q){ e.preventDefault(); q.focus(); }
});

/* ------------------------------------------------------------- citations */
var pop = document.getElementById('cite-pop');
var hideT = null, curRef = null;
function fill(key){
  var li = document.getElementById('fn-' + key);
  if (!li || !pop) return false;
  pop.replaceChildren();
  var c = li.cloneNode(true);            /* cloneNode, never innerHTML: survives trusted-types */
  c.removeAttribute('id');
  c.querySelectorAll('[id]').forEach(function(n){ n.removeAttribute('id'); });
  c.querySelectorAll('.footnote-backref').forEach(function(n){ n.remove(); });
  pop.append(c);
  return true;
}
function place(a){
  var r = a.getBoundingClientRect(), b = pop.getBoundingClientRect(), pad = 10;
  var x = Math.min(Math.max(pad, r.left + r.width / 2 - b.width / 2), innerWidth - b.width - pad);
  var y = r.top - b.height - 8;
  if (y < pad) y = r.bottom + 8;
  pop.style.left = x + 'px';
  pop.style.top = y + 'px';
}
function openPop(a){
  if (!pop || !pop.showPopover) return;
  clearTimeout(hideT);
  if (!fill(a.dataset.fnkey)) return;
  curRef = a;
  if (!pop.matches(':popover-open')) pop.showPopover();   /* must precede place(): no box until
                                                             it is in the top layer */
  place(a);
}
function closePop(){
  hideT = setTimeout(function(){
    if (pop && pop.matches(':popover-open')) pop.hidePopover();
    curRef = null;
  }, 160);                                                /* WCAG 1.4.13 Hoverable */
}
if (pop){
  pop.addEventListener('pointerenter', function(){ clearTimeout(hideT); });
  pop.addEventListener('pointerleave', closePop);
  [].slice.call(document.querySelectorAll('.cite-ref')).forEach(function(a){
    a.addEventListener('pointerenter', function(e){ if (e.pointerType !== 'touch') openPop(a); });
    a.addEventListener('pointerleave', function(e){ if (e.pointerType !== 'touch') closePop(); });
    a.addEventListener('focus', function(){ openPop(a); });
    a.addEventListener('keydown', function(e){
      if (e.key === 'Tab' && !e.shiftKey && pop.matches(':popover-open')){
        var l = pop.querySelector('a[href]');
        if (l){ e.preventDefault(); l.focus(); }
      }
    });
  });
  /* focusout with a relatedTarget check, never blur: blur fires on the marker the instant a
     keyboard user Tabs toward the link inside the popover, destroying it mid-reach. */
  document.addEventListener('focusout', function(e){
    var to = e.relatedTarget;
    if (to && (pop.contains(to) || to === curRef)) return;
    if (pop.matches(':popover-open')) closePop();
  });
  addEventListener('scroll', function(){
    if (pop.matches(':popover-open') && curRef) place(curRef);
  }, { passive: true });
}

/* --------------------------------------------------------- back / forward
   Native fragment navigation already restores the exact pre-jump scroll position, in every
   engine and inside this sandbox. So this is a *labelled wrapper* around history.back(), not a
   reimplementation: what is actually missing in an embedded panel with no browser chrome is the
   reader knowing that Back is safe to press. history.scrollRestoration is never touched — set to
   'manual' it measurably leaves the reader at the jump target, the exact failure this prevents. */
var wrap = document.querySelector('.jump');
var backBtn = document.getElementById('jump-back');
var fwdBtn = document.getElementById('jump-fwd');
var jumpLbl = document.getElementById('jump-label');
var status = document.getElementById('jump-status');
var frames = [], depth = 0, pending = null, pendT = null, dismissed = false;
try { history.replaceState({ d: 0 }, ''); } catch (err) {}

function labelAt(y){
  var probe = y + LINE(), lo = 0, hi = tops.length - 1, i = -1;
  while (lo <= hi){ var m = (lo + hi) >> 1; if (tops[m] <= probe){ i = m; lo = m + 1; } else hi = m - 1; }
  return i < 0 ? 'the top' : heads[i].textContent.trim();
}
function renderJump(){
  if (!wrap) return;
  var f = frames[depth - 1];
  var near = f && Math.abs(scrollY - f.y) < innerHeight * 0.5;
  wrap.hidden = depth === 0 || !f || !!near || dismissed;
  if (f && jumpLbl){
    jumpLbl.textContent = 'Back to ' + f.label;
    backBtn.setAttribute('aria-label', 'Back to ' + f.label);
  }
  if (fwdBtn) fwdBtn.hidden = depth >= frames.length;
}
document.addEventListener('click', function(e){
  var a = e.target.closest('a[href^="#"]');
  if (!a) return;
  var href = a.getAttribute('href');
  if (href === '#') return;
  var id = decodeURIComponent(href.slice(1));
  if (!document.getElementById(id)) return;
  /* No preventDefault: native fragment nav does the scrolling and sets :target. Commit on
     hashchange, not here — clicking an already-current anchor creates no history entry and
     fires no hashchange, so a click-committed stack would desynchronise permanently. */
  pending = { label: labelAt(scrollY), y: scrollY, src: a };
  clearTimeout(pendT);
  pendT = setTimeout(function(){ pending = null; }, 500);
});
addEventListener('hashchange', function(){
  if (pending){
    frames[depth] = pending;
    frames.length = depth + 1;                 /* truncate any forward branch */
    depth++;
    try { history.replaceState({ d: depth, label: pending.label, y: pending.y }, ''); } catch (err) {}
    pending = null;
  }
  dismissed = false;
  var el = document.getElementById(decodeURIComponent(location.hash.slice(1)));
  if (el){
    if (!el.hasAttribute('tabindex') && !el.matches('a,button,input,select,textarea')) el.tabIndex = -1;
    el.focus({ preventScroll: true });         /* preventScroll: a bare focus() re-scrolls and
                                                  lands at a different offset than
                                                  scroll-margin-top */
  }
  renderJump();
});
/* popstate is UI-sync only. Never scrollTo() here — the UA's own restoration runs after this
   handler, so anything written now is overwritten a frame later. */
addEventListener('popstate', function(e){
  depth = (e.state && e.state.d) || 0;
  renderJump();
});
if (backBtn) backBtn.addEventListener('click', function(){
  if (depth <= 0) return;      /* hard gate: this iframe shares the host's session history, so a
                                  back() that is not consuming one of our own entries would
                                  navigate the host away. */
  var f = frames[depth - 1];
  history.back();
  requestAnimationFrame(function(){ requestAnimationFrame(function(){
    if (f && f.src && f.src.isConnected) f.src.focus({ preventScroll: true });
    if (status && f) status.textContent = 'Returned to ' + f.label;
  }); });
});
if (fwdBtn) fwdBtn.addEventListener('click', function(){
  if (depth < frames.length) history.forward();
});
addEventListener('keydown', function(e){
  if (e.key === 'Escape' && wrap && !wrap.hidden){ dismissed = true; renderJump(); }
});

/* ------------------------------------------------------------------ wiring */
addEventListener('scroll', function(){
  if (!queued){ queued = true; requestAnimationFrame(pick); }
  if (wrap && !wrap.hidden) renderJump();
}, { passive: true });
addEventListener('resize', function(){ barHeight(); measure(); pick(); });
/* 23 tables sit in overflow-x wrappers whose height changes with viewport width, which
   invalidates every cached offset. */
new ResizeObserver(function(){ measure(); pick(); }).observe(article);
if (document.fonts && document.fonts.ready) document.fonts.ready.then(function(){ measure(); pick(); });

barHeight();
measure();
nav.setAttribute('data-js', '');     /* last: the no-JS state is fully expanded */
if (bar) nav.dataset.panel = 'closed';
pick();

/* If the host sizes the iframe to content and scrolls the outer window, sticky never engages and
   no scroll event ever fires here — so a collapsed rail would be permanently collapsed with no
   way to see the rest. Ship expanded in that case. */
function embedGuard(){
  if (document.documentElement.scrollHeight <= innerHeight + 4) nav.removeAttribute('data-js');
}
embedGuard();
addEventListener('scroll', embedGuard, { once: true, passive: true });
})();
"""


def build_nav(toc_tokens: list) -> str:
    """One nav, rendered once. Two copies would put aria-current on two links for the same id."""
    out = ['<ol class="toc-list">']
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


def mark_numeric_cells(body: str) -> str:
    """Tag purely numeric table cells so they take the mono, right-aligned, tabular treatment."""

    def one(m: re.Match) -> str:
        attrs, inner = m.group(1), m.group(2)
        plain = re.sub(r"<[^>]+>", "", inner).strip()
        numeric = plain and re.fullmatch(r"[−–—\-+]?[\d.,]+\s*(×|x|%)?", plain)
        cls = ' class="num"' if numeric else ""
        return f"<td{cls}{attrs}>{inner}</td>"

    return re.sub(r"<td([^>]*)>(.*?)</td>", one, body, flags=re.S)


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


def check_ref_order(md_text: str, front: str) -> None:
    """python-markdown numbers footnotes by definition order, GitHub by first-reference order.

    If they disagree, the same citation is note 9 here and note 1 on github.com. Strip code spans
    and fences first: the document contains regex literals like `[^>]+` that would otherwise be
    read as citations.
    """
    t = re.sub(r"```.*?```", "", md_text, flags=re.S)
    t = re.sub(r"`[^`\n]*`", "", t)
    first = list(dict.fromkeys(m.group(1) for m in re.finditer(r"\[\^([^\]\s]+)\](?!:)", t)))
    defs = re.findall(r"^\[\^([^\]]+)\]:", md_text, re.M)
    if defs != first:
        raise SystemExit(
            "docs/METHOD.md: reorder the [^key]: definitions to first-reference order:\n  "
            + ", ".join(first)
        )
    if "[^" in front:
        raise SystemExit("docs/METHOD.md: citations are not supported above '## 1.' (the lede)")


def render(md_text: str) -> str:
    # Split the h1 and its lede off the body so the hero can be composed explicitly.
    split = re.search(r"^## 1\. ", md_text, re.M)
    front, body_md = md_text[: split.start()], md_text[split.start():]
    check_ref_order(md_text, front)

    title = re.search(r"^# (.+)$", front, re.M).group(1)
    lede_md = "\n".join(
        line
        for line in front.splitlines()[1:]
        if line.strip() and not line.startswith("#") and not line.startswith("---")
    )

    md = markdown.Markdown(
        extensions=["tables", "fenced_code", "toc", "attr_list", "sane_lists", "footnotes"],
        extension_configs={
            "toc": {"toc_depth": "2-3", "permalink": False},
            # "-" keeps ids as fn-key / fnref-key rather than colon-separated.
            "footnotes": {"SEPARATOR": "-"},
        },
    )
    body = md.convert(body_md)
    toc_tokens = md.toc_tokens  # capture before any reset() clears it
    lede = markdown.Markdown(extensions=["sane_lists"]).convert(lede_md)

    body = mark_numeric_cells(body)
    body = transform_refs(body)
    body = body.replace("<table>", '<div class="tw"><table>').replace("</table>", "</table></div>")
    nav = build_nav(toc_tokens)

    # charset first: the HTML encoding prescan only looks at the first 1024 bytes, and without it
    # a standalone `out/method.html` is decoded as Latin-1 — every em dash becomes "â€”" and the
    # backref arrows turn to mojibake. Harmless when a publishing wrapper supplies its own head.
    return f"""<meta charset="utf-8">
<title>Measuring Go Puzzle Difficulty</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>{CSS}</style>
<header class="hero" id="top"><div class="shell"><div class="hero-in">
  <p class="eyebrow">Method note &middot; gomagic-glicko</p>
  <h1>{html.escape(title)}</h1>
  <div class="lede">{lede}</div>
  {motif()}
</div></div></header>
<div class="shell"><div class="layout">
  <nav class="toc" aria-label="Contents">
    <div class="toc-bar">
      <button id="tocbtn" type="button" aria-expanded="false" aria-controls="toc-list">
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
</div>
<p id="jump-status" role="status" aria-live="polite" class="sr-only"></p>
<script>{JS}</script>
"""


def check_js(js: str) -> str:
    """Syntax-check the inlined script if a JS engine is around.

    Worth the eight lines: a parse-time SyntaxError anywhere in this script kills *all* of it, so
    the page silently degrades to a fully-expanded rail with no scroll-spy, no citations popover
    and no back control — and it still looks fine in a screenshot. That is exactly how the
    combining-marks regex above shipped once. Skipped, not fatal, when no engine is installed.
    """
    exe = shutil.which("node") or shutil.which("bun")
    if not exe:
        print("  (no node/bun on PATH — skipped the JS syntax check)")
        return js
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
        fh.write(js)
        tmp = fh.name
    try:
        r = subprocess.run([exe, "--check", tmp], capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit("inlined JS failed to parse:\n" + (r.stderr or r.stdout))
    finally:
        os.unlink(tmp)

    # Narrower than "no non-ASCII anywhere" — em dashes in comments are fine. What is not fine is
    # a raw non-ASCII character inside a character class, which is how the combining-marks range
    # became the invalid /[Ì€-Í¯]/ after a re-encode. Escapes only, in there.
    for cls in re.findall(r"\[(?:[^\]\\\n]|\\.)*\]", js):
        bad = [c for c in cls if not c.isascii()]
        if bad:
            raise SystemExit(
                f"inlined JS: non-ASCII character(s) {bad!r} inside the character class {cls!r}. "
                "Write them as \\uXXXX escapes — a re-encode turns them into an invalid range, "
                "which is a parse-time error that silently disables the whole script."
            )
    return js


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--out", type=Path, default=ROOT / "out" / "method.html")
    args = ap.parse_args()

    check_js(JS)
    page = render(SRC.read_text())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(page)
    print(f"  wrote {args.out}  ({len(page):,} bytes)\n")


if __name__ == "__main__":
    main()
