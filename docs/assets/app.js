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
/* One source of truth for both the anchor outset and the spy probe: --read-line is registered as
   a <length> in CSS, so this always reads a resolved pixel value. */
function LINE(){
  return parseFloat(getComputedStyle(document.documentElement)
                    .getPropertyValue('--read-line')) + 24;
}
function measure(){
  tops = heads.map(function(h){ return h.getBoundingClientRect().top + scrollY; });
}
/* Index of the last heading at or above `y`, or -1 when `y` is above the first one. The scroll-spy
   and the back-pill label both ask this question, so they ask it in one place. */
function idxAt(y){
  var lo = 0, hi = tops.length - 1, i = -1;
  while (lo <= hi){ var m = (lo + hi) >> 1; if (tops[m] <= y){ i = m; lo = m + 1; } else hi = m - 1; }
  return i;
}
function pick(){
  queued = false;
  var doc = document.documentElement;
  /* Tail clamp: the last heading can sit too near the document end to ever reach the probe. */
  if (scrollY + innerHeight >= doc.scrollHeight - 2) return set(heads.length - 1);
  set(Math.max(0, idxAt(scrollY + LINE())));
}
function set(i){ if (i === cur || i < 0) return; cur = i; applyActive(heads[i]); }
/* One rAF per scroll burst does both jobs. renderJump used to be called from the scroll listener
   behind `!wrap.hidden`, which is the state renderJump itself computes — a one-way latch: once the
   pill hid, no amount of scrolling could bring it back. */
function onFrame(){ pick(); renderJump(); }

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
    if (s === li) s.setAttribute('data-open','');
    else if (!s.hasAttribute('data-pinned')) s.removeAttribute('data-open');
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
  var i = idxAt(y + LINE());
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
    /* Only `d` is ever read back (in popstate). The label and scroll position live in `frames`,
       which is the same lifetime, so stamping them here was write-only state. */
    try { history.replaceState({ d: depth }, ''); } catch (err) {}
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
  /* A *new* fragment navigation also fires popstate (with a null state) just before hashchange.
     Letting that reset depth pinned the stack at 1 and truncated frames on every jump, so the
     forward button never appeared and Back went to the wrong place. If a commit is pending, this
     is that synthetic event: leave depth alone and let hashchange own it. */
  if (pending) return;
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
  /* Only dismiss the pill if Escape was not already spent closing the popover, and not while
     focus is inside the rail's filter (where Escape clears the query). */
  if (e.key !== 'Escape' || !wrap || wrap.hidden) return;
  if (pop && pop.matches(':popover-open')) return;
  if (e.target === q) return;
  dismissed = true;
  renderJump();
});

/* ------------------------------------------------------------------ wiring */
addEventListener('scroll', function(){
  if (!queued){ queued = true; requestAnimationFrame(onFrame); }
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
