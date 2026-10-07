"""Shared styling and presentational components ("proof sheet" system).

Paper and ink chrome stays quiet so each business's own brand carries the
previews. The marker is reserved for one job: showing the single thing a
test changes, and the value that won.
"""
import html
import re

import streamlit as st

import agent

CSS = """
<style>
:root {
  --paper: #FBF8F3; --paper-2: #F3EEE5; --sheet: #FFFDF9;
  --ink: #1C1A17; --ink-2: #4F4941; --ink-3: #6B6358;
  --rule: #E4DCCF; --rule-strong: #CFC5B5;
  --marker: #FFD84D; --marker-soft: #FFF3C4;
  --serif: "Newsreader", Georgia, serif;
}
::selection { background: var(--marker); color: var(--ink); }
#MainMenu, footer, [data-testid="stToolbar"] { visibility: hidden; }
.block-container { padding-top: 2.25rem; max-width: 1180px; }
h1 { letter-spacing: -0.02em; font-weight: 500 !important; }
h2 { letter-spacing: -0.01em; font-weight: 500 !important; }
[data-testid="stMarkdownContainer"] table, .num { font-variant-numeric: tabular-nums; }

/* Visible focus on every text field (Streamlit removes the outline). */
[data-baseweb="textarea"]:focus-within, [data-baseweb="input"]:focus-within {
  outline: 2px solid var(--ink); outline-offset: 2px; }
a:focus-visible, button:focus-visible, [role="radio"]:focus-visible, [role="tab"]:focus-visible {
  outline: 2px solid var(--ink) !important; outline-offset: 2px; }

section[data-testid="stMain"]:focus-visible { outline: 2px solid var(--ink); outline-offset: -4px; }

.page-sub { color: var(--ink-2); margin: -0.5rem 0 1.75rem; font-size: 1.02rem; max-width: 62ch; }
.muted { color: var(--ink-3); font-size: 0.92rem; }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }

/* Tags: small, square, printed */
.tag { display: inline-block; padding: 1px 8px; border-radius: 3px; font-size: 12px; font-weight: 600;
       letter-spacing: .01em; border: 1px solid var(--rule-strong); color: var(--ink-2); background: var(--sheet);
       margin-right: 6px; white-space: nowrap; vertical-align: middle; }
.tag-sim { border-color: var(--ink); color: var(--ink); }
.tag-warn { border-color: #C9A227; background: #FFF8DD; color: #6B4E00; }
.tag-ok { border-color: #8FB59C; background: #EEF6F0; color: #1D5134; }

/* Steps */
.step { display: flex; align-items: center; gap: 14px; margin: 2rem 0 0.75rem; }
.step-num { width: 30px; height: 30px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
            font-weight: 700; font-size: 14px; flex-shrink: 0; background: var(--ink); color: var(--paper); }
.step-num.done { background: transparent; color: var(--ink); border: 1.5px solid var(--ink); }
.step-num.todo { background: transparent; color: var(--ink-2); border: 1.5px dashed var(--rule-strong); }
.step-title { font-weight: 650; font-size: 1.12rem; color: var(--ink); line-height: 1.25; }
.step-sub { color: var(--ink-2); font-size: 0.92rem; }
.step.todo .step-title { color: var(--ink-2); font-weight: 600; }

/* The marker */
mark.mk { background: linear-gradient(transparent 12%, var(--marker) 12%, var(--marker) 88%, transparent 88%);
          color: inherit; padding: 0 .12em; border-radius: 2px; -webkit-box-decoration-break: clone; box-decoration-break: clone; }
.mk-ghost { text-decoration: underline dotted var(--ink-3); text-underline-offset: 4px; text-decoration-thickness: 1.5px; }

/* The test: serif statement + meta */
.statement { font-family: var(--serif); font-size: clamp(1.6rem, 2.6vw, 2.15rem); line-height: 1.28;
             font-weight: 500; color: var(--ink); margin: 0 0 10px; letter-spacing: -0.01em; max-width: 30ch;
             text-wrap: balance; }
.meta { color: var(--ink-2); font-size: 0.9rem; display: flex; flex-wrap: wrap; gap: 4px 0; align-items: center; }
.meta > span + span::before { content: "·"; margin: 0 10px; color: var(--ink-3); }
.meta b { color: var(--ink); font-weight: 600; }
.diffline { display: none; font-size: 0.92rem; color: var(--ink-2); margin: 4px 0 10px; }

.why-h { font-size: 0.95rem; font-weight: 650; margin: 0 0 8px; color: var(--ink); }
.evidence { list-style: none; padding: 0; margin: 0; }
.evidence li { padding: 7px 0 7px 18px; position: relative; border-bottom: 1px solid var(--rule); font-size: 0.95rem; }
.evidence li:last-child { border-bottom: none; }
.evidence li::before { content: ""; position: absolute; left: 2px; top: 15px; width: 6px; height: 6px;
                       border-radius: 50%; background: var(--ink); }
.prose { color: var(--ink); font-size: 0.95rem; line-height: 1.55; max-width: 60ch; }
.expect { margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--rule); color: var(--ink-2); font-size: 0.92rem; }

/* Variant labels */
.vlabel { display: flex; align-items: baseline; gap: 10px; margin-bottom: 8px; }
.vletter { font-family: var(--serif); font-size: 1.6rem; line-height: 1; font-weight: 500; }
.vdesc { color: var(--ink-2); font-size: 0.92rem; }

/* Previews: a printed proof of the owner's own brand */
.mock { background: #fff; color: #111; border: 1px solid var(--rule); border-radius: 6px;
        box-shadow: 0 1px 2px rgba(28,26,23,.08), 0 3px 8px -4px rgba(28,26,23,.16); overflow: hidden; }
.art { display: block; font-size: 11px; font-weight: 700; letter-spacing: .04em; opacity: .85; margin-bottom: 2px; }
.mail-top { padding: 14px 16px; border-bottom: 1px solid #f0ebe3; display: flex; gap: 10px; align-items: center; }
.avatar { width: 36px; height: 36px; border-radius: 50%; object-fit: cover; flex-shrink: 0; background: #fff;
          border: 1px solid #eee; display: flex; align-items: center; justify-content: center; color: #fff; font-weight: 700; }
.mail-from { font-weight: 600; font-size: 14px; }
.mail-meta { color: #5f5f5f; font-size: 12px; }
.mail-subject { font-weight: 700; font-size: 17px; padding: 14px 16px 0; line-height: 1.35; }
.mail-body { padding: 8px 16px 4px; font-size: 14px; color: #333; line-height: 1.55; }
.hero { margin: 12px 16px; border-radius: 4px; height: 112px; display: flex; align-items: flex-end;
        padding: 10px 12px; font-size: 12.5px; font-weight: 500; }
.btn { display: inline-block; margin: 6px 16px 18px; padding: 9px 18px; border-radius: 4px; font-weight: 600; font-size: 14px; }
.ig-top { display: flex; align-items: center; gap: 10px; padding: 10px 12px; }
.ig-handle { font-weight: 600; font-size: 14px; }
.ig-media { height: 280px; display: flex; flex-direction: column; justify-content: space-between; padding: 14px; font-size: 13.5px; font-weight: 500; }
.ig-format { align-self: flex-start; font-size: 11.5px; font-weight: 700; letter-spacing: .04em;
             background: rgba(0,0,0,.28); color: #fff; padding: 3px 9px; border-radius: 999px; }
.ig-format mark.mk, .hero mark.mk, .btn mark.mk { color: var(--ink); }
.ig-format .mk-ghost, .hero .mk-ghost, .btn .mk-ghost { text-decoration-color: rgba(255,255,255,.85); }
.ig-icons { padding: 10px 12px 0; display: flex; gap: 16px; color: #111; }
.ig-caption { padding: 6px 12px 14px; font-size: 14px; line-height: 1.5; }
.ig-tags { color: #00376B; }
.when { font-size: 12px; color: #5f5f5f; padding: 0 12px 12px; }

/* Results */
.verdict { font-family: var(--serif); font-size: clamp(2rem, 3.4vw, 2.7rem); line-height: 1.15; font-weight: 500;
           letter-spacing: -0.015em; margin: 6px 0 6px; max-width: 26ch; text-wrap: balance; }
.legend { font-size: 0.85rem; color: var(--ink-3); margin-top: 8px; line-height: 1.5; }
.verdict-sub { font-size: 1.05rem; color: var(--ink-2); margin-bottom: 18px; max-width: 60ch; }
table.ab { width: 100%; border-collapse: collapse; font-size: 0.95rem; }
table.ab th { text-align: right; font-weight: 600; color: var(--ink-2); font-size: 0.82rem; padding: 6px 10px;
              border-bottom: 1.5px solid var(--ink); }
table.ab th:first-child, table.ab td:first-child { text-align: left; }
table.ab td { text-align: right; padding: 9px 10px; border-bottom: 1px solid var(--rule); font-variant-numeric: tabular-nums; }
table.ab tr.primary td { font-weight: 700; }
.up { color: #1D5134; } .down { color: #8A2B1F; }
.lesson-quote { font-family: var(--serif); font-size: 1.2rem; line-height: 1.45; color: var(--ink); margin: 4px 0 0; max-width: 62ch; }

/* Playbook strip: memory made visible */
.playbook { border-top: 1px solid var(--rule); border-bottom: 1px solid var(--rule); padding: 10px 0; margin: 4px 0 2px;
            font-size: 0.92rem; color: var(--ink-2); line-height: 1.9; }
.playbook b { color: var(--ink); }
.pb-item { display: inline-block; margin: 0 4px 0 0; padding: 0 8px; border-radius: 3px; background: var(--marker-soft);
           color: var(--ink); border: 1px solid #EBD98C; line-height: 1.6; }

/* Lessons list (Overview) */
.lesson { padding: 9px 0; border-bottom: 1px solid var(--rule); font-size: 0.93rem; line-height: 1.45; }
.lesson:last-child { border-bottom: none; }
.lesson .ch { color: var(--ink-3); font-size: 0.8rem; font-weight: 600; text-transform: capitalize; margin-right: 6px; }

/* Home: the guided path */
.journey { border-top: 1.5px solid var(--ink); margin-top: 6px; }
.jstep { display: flex; gap: 18px; align-items: flex-start; padding: 20px 0 6px; }
.jnum { font-family: var(--serif); font-size: 2rem; line-height: 1; width: 34px; flex-shrink: 0; color: var(--ink); }
.jstep.done .jnum, .jstep.later .jnum { color: var(--ink-3); }
.jtitle { font-weight: 650; font-size: 1.12rem; color: var(--ink); line-height: 1.3; }
.jstep.later .jtitle { color: var(--ink-2); font-weight: 600; }
.jdesc { color: var(--ink-2); font-size: 0.95rem; margin-top: 3px; max-width: 58ch; line-height: 1.5; }
.jstate { margin-top: 8px; }
.jrule { border-bottom: 1px solid var(--rule); margin-top: 14px; }
.lede { font-family: var(--serif); font-size: 1.35rem; line-height: 1.4; color: var(--ink); max-width: 40ch;
        margin: 0 0 6px; text-wrap: balance; }
[data-testid="stMarkdownContainer"] p.lede { font-size: 1.35rem !important; }
.nextcard { border: 1px solid var(--rule); background: var(--sheet); border-radius: 6px; padding: 22px 24px 8px; }

.empty { border: 1px dashed var(--rule-strong); border-radius: 6px; padding: 28px; text-align: center; background: var(--sheet); }

/* Sticky run bar keeps the one action in reach on long pages and phones. */
[data-testid="stLayoutWrapper"]:has(> .st-key-runbar) { position: sticky; bottom: 0; z-index: 20; }
.st-key-runbar { background: var(--paper); border-top: 1px solid var(--rule); padding: 12px 0 10px; margin-top: 8px; }
/* Serif moments: beat Streamlit's paragraph sizing. */
[data-testid="stMarkdownContainer"] p.statement { font-size: clamp(1.6rem, 2.6vw, 2.15rem) !important; line-height: 1.2; }
[data-testid="stMarkdownContainer"] p.verdict { font-size: clamp(2rem, 3.4vw, 2.7rem) !important; line-height: 1.12; }
[data-testid="stMarkdownContainer"] p.lesson-quote { font-size: 1.2rem !important; line-height: 1.45; }

.only-mobile { display: none; }
@media (max-width: 640px) {
  .only-mobile { display: inline; }
  .only-desktop { display: none; }
  .diffline { display: block; }
  .stButton button, [data-testid="stPopover"] button, [data-testid="stButtonGroup"] button,
  [data-testid="stExpander"] summary { min-height: 44px; }
  .block-container { padding-left: 1rem; padding-right: 1rem; padding-top: 1.25rem; }
  [data-testid="stMarkdownContainer"] p.statement { font-size: 1.45rem !important; }
  [data-testid="stMarkdownContainer"] p.verdict { font-size: 1.8rem !important; }
  .st-key-runbar { padding: 8px 0 6px; }
  .st-key-runbar [data-testid="stHorizontalBlock"] { flex-wrap: wrap; gap: 8px; }
  .st-key-runbar [data-testid="stColumn"] { width: calc(50% - 4px) !important; flex: 1 1 calc(50% - 4px) !important; min-width: 0; }
  .st-key-runbar [data-testid="stColumn"]:last-child { flex-basis: 100% !important; width: 100% !important; }
  .st-key-runbar button p { font-size: 0.88rem; }
  .ig-media { height: 220px; }
  .step { margin-top: 1.5rem; }
}
</style>
"""

ICONS = {  # 1.75px stroke, decorative glyphs for the Instagram proof
    "heart": '<path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/>',
    "comment": '<path d="M20 12a8 8 0 1 1-3.1-6.3A8 8 0 0 1 20 12z"/><path d="M20 20l-3.2-1.3"/>',
    "send": '<path d="M21 3 3 10.5l7 2.5 2.5 7z"/><path d="M10 13l11-10"/>',
}


def icon(name):
    return (f'<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            f'{ICONS[name]}</svg>')


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def esc(text) -> str:
    """HTML-escape text; `inline code` spans become bold (owners never see code styling)."""
    return re.sub(r"`([^`]+)`", r"<b>\1</b>", html.escape(str(text or "")))


def tag(text, kind="") -> str:
    return f'<span class="tag {("tag-" + kind) if kind else ""}">{html.escape(text)}</span>'


def mark(text_html: str, phrase: str) -> str:
    """Wrap the first occurrence of phrase (case-insensitive) in the marker."""
    p = html.escape(phrase)
    i = text_html.lower().find(p.lower())
    if not p or i < 0:
        return text_html
    return f'{text_html[:i]}<mark class="mk">{text_html[i:i + len(p)]}</mark>{text_html[i + len(p):]}'


def page_header(title, subtitle=""):
    st.title(title, anchor=False)
    if subtitle:
        st.markdown(f'<div class="page-sub">{html.escape(subtitle)}</div>', unsafe_allow_html=True)


def step(n, title, subtitle="", state="active"):
    cls = {"done": "done", "todo": "todo"}.get(state, "")
    num = "✓" if state == "done" else n
    status = {"done": "done", "todo": "not started"}.get(state, "current step")
    st.markdown(
        f'<div class="step {cls}"><div class="step-num {cls}" aria-hidden="true">{num}</div><div>'
        f'<div class="step-title" role="heading" aria-level="2">{html.escape(title)}'
        f'<span class="sr-only"> (step {n}, {status})</span></div>'
        f'<div class="step-sub">{html.escape(subtitle)}</div></div></div>', unsafe_allow_html=True)


def fmt(v):
    return f"{v:,}" if isinstance(v, int) else f"{v:.2%}"


def metric_label(m):
    return agent.METRIC_LABELS.get(m, m.replace("_", " ").capitalize())


CONFIDENCE = {"low": ("First time testing this", "no past result for this setting yet"),
              "medium": ("Good bet", "this setting has a past result"),
              "high": ("Strong evidence", "several past results agree")}


# ---------------- the test ----------------
def test_statement(s: dict, channel: str, source: str, n_tests: int, error: str | None = None):
    new_phrase = agent.option_label(channel, s["test_dimension"], s["challenger_value"])
    title, why = CONFIDENCE.get(s["confidence"], CONFIDENCE["low"])
    import strategist
    if source != "offline":
        writer = f"Written by {strategist.writer_name(source)}"
    elif error:
        writer = "Template copy: the AI writer's plan couldn't be used"
    else:
        writer = "Template copy: AI writer offline"
    basis = f"Based on {n_tests} past test{'s' if n_tests != 1 else ''}" if n_tests else "No past tests yet"
    st.markdown(f'<p class="statement">{mark(esc(s["recommendation"]), new_phrase)}</p>'
                f'<div class="meta"><span><b>{title}</b>: {why}</span><span>{basis}</span>'
                f'<span>{writer}</span></div>', unsafe_allow_html=True)


def why_section(s: dict):
    left, right = st.columns([1, 1], gap="large")
    with left:
        st.markdown('<div class="why-h" role="heading" aria-level="3">What your past tests show</div>'
                    '<ul class="evidence">' + "".join(f"<li>{esc(i)}</li>" for i in s["insights"]) + "</ul>",
                    unsafe_allow_html=True)
    with right:
        st.markdown(f'<div class="why-h" role="heading" aria-level="3">Why this change</div>'
                    f'<div class="prose">{esc(s["rationale"])}</div>'
                    f'<div class="expect"><b>We expect:</b> {esc(s["hypothesis"])}</div>', unsafe_allow_html=True)


# ---------------- variant previews ----------------
def _lum(hex_):
    h = hex_.lstrip("#")
    rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def readable_on_white_text(hex_, fallback="#1C1A17"):
    """Darken a brand color until white text on it passes WCAG AA (4.5:1)."""
    try:
        h = hex_.lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        rgb = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    except (ValueError, AttributeError, IndexError):
        return fallback
    for _ in range(40):
        c = "#%02x%02x%02x" % tuple(rgb)
        if 1.05 / (_lum(c) + 0.05) >= 4.5:
            return c
        rgb = [int(v * 0.94) for v in rgb]
    return fallback


# Which part of the proof each tested dimension changes.
PART = {"subject_hook": "headline", "personalization": "headline", "emoji": "headline", "hook": "headline",
        "offer": "body", "cta": "cta", "hashtags": "tags", "send_time": "when", "post_time": "when",
        "format": "format"}


def _avatar(brand, logo, color):
    if logo:
        return f'<img class="avatar" src="{html.escape(logo)}" alt="{html.escape(brand)} logo">'
    initials = "".join(w[0] for w in brand.split()[:2]).upper() or "B"
    return f'<div class="avatar" style="background:{color}" aria-hidden="true">{html.escape(initials)}</div>'


SENTENCE = re.compile(r"((?<=[.!?])[ \t]+|\n+)")


def _diff_html(text, other, letter, changed):
    """Escape text; in B wrap sentences/lines absent from A in the marker, in A underline the
    ones B replaces. Line breaks are kept. `changed` forces the whole field."""
    if changed is None:
        changed = text.strip() != other.strip()
    if not changed:
        return esc(text).replace("\n", "<br>")
    others = {t.strip() for t in SENTENCE.split(other) if t.strip()}
    out = []
    for i, part in enumerate(SENTENCE.split(text)):
        if i % 2:  # separator
            out.append("<br>" if "\n" in part else " ")
        elif part.strip() and part.strip() not in others:
            out.append(_mark_one(part, letter))
        else:
            out.append(esc(part))
    return "".join(out)


def _mark_one(text, letter, html_ready=False):
    inner = text if html_ready else esc(text)
    if letter == "B":
        return f'<mark class="mk"><span class="sr-only">Changed: </span>{inner}</mark>'
    return f'<span class="mk-ghost">{inner}</span>'


def variant_preview(channel, copy, other, cfg, changed_dim, letter, brand, profile):
    """A printed proof of one version. `other` is the other version's copy, used to mark
    exactly what differs; send time and post format come from the tested setting."""
    colors = profile.get("colors") or {}
    c1 = readable_on_white_text(colors.get("primary") or "#3A5A40")
    c2 = readable_on_white_text(colors.get("secondary") or "#1C1A17")
    logo = profile.get("logo")
    part = PART.get(changed_dim)

    def f(key):  # a copy field, diffed against the other version
        return _diff_html(copy[key], other[key], letter, None).replace("{first_name}", "Alex")

    def cfg_part(key, text):  # parts driven by the config, not the copy
        return _mark_one(text, letter) if key == part else esc(text)

    art = f'<span class="art">Image idea</span>{f("visual")}'
    if channel == "email":
        when = "8:04 AM" if cfg.get("send_time") == "morning" else "7:12 PM"
        body = (f'<div class="mail-top">{_avatar(brand, logo, c1)}<div>'
                f'<div class="mail-from">{html.escape(brand)}</div>'
                f'<div class="mail-meta">to Alex · {cfg_part("when", when)}</div></div></div>'
                f'<div class="mail-subject">{f("headline")}</div>'
                f'<div class="mail-body">{f("body")}</div>'
                f'<div class="hero" style="background:linear-gradient(135deg,{c1},{c2});color:#fff">'
                f'<div>{art}</div></div>'
                f'<span class="btn" style="background:{c1};color:#fff">{f("cta")}</span>')
        kind = "email"
    else:
        handle = (profile.get("insta_handle") or brand.lower().replace(" ", "")).lstrip("@")
        fmt_ = {"reel": "Reel", "carousel": "Carousel · 1/5", "single_image": "Photo"}.get(cfg.get("format"), "Post")
        tags, otags = (" ".join(re.findall(r"#\w+", c["body"])) for c in (copy, other))
        text = re.sub(r"#\w+", "", copy["body"]).strip()
        otext = re.sub(r"#\w+", "", other["body"]).strip()
        when = "Posted 8:10 AM" if cfg.get("post_time") == "morning" else "Posted 7:30 PM"
        body = (f'<div class="ig-top">{_avatar(brand, logo, c1)}'
                f'<div class="ig-handle">{html.escape(handle)}</div></div>'
                f'<div class="ig-media" style="background:linear-gradient(160deg,{c1},{c2});color:#fff">'
                f'<span class="ig-format">{cfg_part("format", fmt_)}</span><div>{art}</div></div>'
                f'<div class="ig-icons">{icon("heart")}{icon("comment")}{icon("send")}</div>'
                f'<div class="ig-caption"><b>{html.escape(handle)}</b> {f("headline")} '
                f'{_diff_html(text, otext, letter, None)} {f("cta")} '
                f'<span class="ig-tags">{_diff_html(tags, otags, letter, None)}</span></div>'
                f'<div class="when">{cfg_part("when", when)}</div>')
        kind = "Instagram post"
    st.markdown(f'<div class="mock" role="group" aria-label="Version {letter} {kind} preview">{body}</div>',
                unsafe_allow_html=True)


def plain_copy(channel, copy) -> str:
    """The winning version as text to paste into an email tool or Instagram."""
    if channel == "email":
        return (f"Subject: {copy['headline']}\n\n{copy['body']}\n\n[Button] {copy['cta']}\n\n"
                f"Image idea: {copy['visual']}").replace("{first_name}", "[First name]")
    return f"{copy['headline']} {copy['body']} {copy['cta']}\n\nImage idea: {copy['visual']}"


# ---------------- results ----------------
def results_table(res):
    rows = []
    for metric in res["results"]["A"]:
        a, b = res["results"]["A"][metric], res["results"]["B"][metric]
        diff = (b - a) / a if a else 0
        cls = "up" if diff > 0 else "down" if diff < 0 else ""
        main = metric == res["primary"]
        rows.append(f'<tr class="{"primary" if main else ""}"><td>{metric_label(metric)}'
                    f'{" (main goal)" if main else ""}</td><td>{fmt(a)}</td><td>{fmt(b)}</td>'
                    f'<td class="{cls}">{diff:+.1%}</td></tr>')
    st.markdown('<table class="ab"><caption class="sr-only">Version A and B results</caption>'
                '<thead><tr><th scope="col">Measure</th><th scope="col">A</th><th scope="col">B</th>'
                '<th scope="col">B vs A</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table>",
                unsafe_allow_html=True)


def lesson_sentence(md: dict) -> str:
    ch, dim = md["channel"], md["dimension"]
    win = agent._cap(agent.option_label(ch, dim, md["winner"]))
    lose = agent.option_label(ch, dim, md["loser"])
    if md.get("tie"):
        return f"{esc(agent._cap(lose))} and {esc(win.lower())}: too close to call."
    return f'<mark class="mk">{esc(win)}</mark> beat {esc(lose)} (+{md.get("lift", 0):.0%}).'


def lessons(learnings, limit=8):
    if not learnings:
        st.markdown('<div class="muted">No lessons yet. Run a test to start learning.</div>',
                    unsafe_allow_html=True)
        return
    rows = [f'<div class="lesson"><span class="ch">{md["channel"]}</span>{lesson_sentence(md)}</div>'
            for md in (m["metadata"] for m in reversed(learnings[-limit:]))]
    st.markdown("".join(rows), unsafe_allow_html=True)


def playbook_strip(learnings, channel):
    """What has won on this channel so far: memory compounding, visible where you plan."""
    wins, tested = {}, 0
    for m in learnings:
        md = m["metadata"]
        if md.get("channel") != channel:
            continue
        tested += 1
        wins[md["dimension"]] = md["winner"]
    name = "Email" if channel == "email" else "Instagram"
    if not tested:
        body = f"<b>{name} playbook:</b> empty for now. Each test you run adds what worked."
    else:
        items = "".join(f'<span class="pb-item">{esc(agent.option_label(channel, d, v))}</span>'
                        for d, v in wins.items())
        body = (f"<b>{name} playbook</b> from {tested} test{'s' if tested != 1 else ''}: {items}"
                f'<span class="muted"> Version A starts from these.</span>')
    st.markdown(f'<div class="playbook">{body}</div>', unsafe_allow_html=True)


def journey_step(n, title, desc, state):
    """One row of the getting-started path. state: done | current | later."""
    badge = {"done": tag("Done", "ok"), "current": tag("Start here", "sim"), "later": ""}[state]
    status = {"done": "done", "current": "current step", "later": "not started"}[state]
    st.markdown(f'<div class="jstep {state}"><div class="jnum" aria-hidden="true">{n}</div><div>'
                f'<div class="jtitle" role="heading" aria-level="2">{html.escape(title)}'
                f'<span class="sr-only"> (step {n}, {status})</span></div>'
                f'<div class="jdesc">{html.escape(desc)}</div>'
                f'<div class="jstate">{badge}</div></div></div>', unsafe_allow_html=True)
