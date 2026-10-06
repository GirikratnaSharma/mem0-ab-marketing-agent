"""Streamlit dashboard for the Mem0 A/B marketing agent."""
import json
import time
import uuid
from datetime import datetime

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv

import agent
from memory_store import DATA_DIR, MemoryStore

load_dotenv()
st.set_page_config(page_title="A/B Marketing Agent · Mem0", page_icon="🧪", layout="wide")

CAMPAIGNS_PATH = DATA_DIR / "campaigns.json"
PROFILE_PATH = DATA_DIR / "profiles.json"
ONBOARD_DIR = DATA_DIR / "business-onboarding"
WEBSITE_SCRAPE_PATH = ONBOARD_DIR / "website.json"
INSTAGRAM_SCRAPE_PATH = ONBOARD_DIR / "instagram.json"


# ---------------- persistence helpers ----------------
def load_json(path, default):
    return json.loads(path.read_text()) if path.exists() else default


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2))


def campaigns_for(user_id):
    return [c for c in load_json(CAMPAIGNS_PATH, []) if c["user_id"] == user_id]


def save_campaign(c):
    data = load_json(CAMPAIGNS_PATH, [])
    data.append(c)
    save_json(CAMPAIGNS_PATH, data)


def fmt(metric, v):
    return f"{v:,}" if isinstance(v, int) else f"{v:.2%}"


@st.cache_data(show_spinner=False, ttl=3600)
def fetch_image(url):
    """Fetch an image server-side. Instagram/CDN hosts hotlink-block direct
    <img src> requests from the browser, so we proxy the bytes through here."""
    if not url:
        return None
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
        r.raise_for_status()
        return r.content
    except Exception:
        return None


# ---------------- onboarding: simulated scrape ----------------
def render_color_swatches(colors):
    swatches = "".join(
        f'<div style="display:inline-block;text-align:center;margin-right:10px">'
        f'<div style="width:42px;height:42px;border-radius:8px;background:{v};'
        f'border:1px solid rgba(0,0,0,0.15)"></div>'
        f'<div style="font-size:11px;margin-top:2px">{k}</div></div>'
        for k, v in colors.items() if isinstance(v, str) and v.startswith("#")
    )
    if swatches:
        st.markdown(swatches, unsafe_allow_html=True)


def run_scrape_animation(website_url, insta_handle):
    """~30s animated 'scrape' of the site + Instagram. Data is canned fixtures
    in data/business-onboarding/ (no live scraping), timed to feel live.
    Each discovery (screenshot, colors, logo, profile, posts) is revealed the
    moment its step completes rather than all at once at the end. The
    progress/status placeholders are cleared when done; the revealed content
    is left on screen and is also redrawn by render_scrape_media() on every
    later rerun."""
    insta_handle = (insta_handle or "").lstrip("@").strip()
    website = load_json(WEBSITE_SCRAPE_PATH, {}).get("data", {})
    insta_list = load_json(INSTAGRAM_SCRAPE_PATH, [])
    insta = insta_list[0] if insta_list else {}
    branding = website.get("branding", {})
    logo = branding.get("images", {}).get("logo") or branding.get("logo")

    status = st.empty()
    bar = st.progress(0)
    shot_area = st.empty()
    colors_area = st.empty()
    logo_area = st.empty()

    for pct, label, pause, reveal in [
        (10, f"🌐 Connecting to {website_url or 'your website'}...", 2.0, None),
        (25, "🌐 Fetching homepage & key pages...", 2.0, "screenshot"),
        (40, "🌐 Reading page content & copy...", 2.0, None),
        (60, "🎨 Extracting color palette & fonts...", 2.2, "colors"),
        (80, "🧬 Detecting logo...", 2.2, "logo"),
        (92, "🧠 Analyzing brand personality & tone...", 2.0, None),
        (100, "✅ Website scrape complete", 1.0, None),
    ]:
        status.markdown(f"**{label}**")
        bar.progress(pct)
        time.sleep(pause)
        if reveal == "screenshot" and website.get("screenshot"):
            with shot_area.container():
                st.image(website["screenshot"], caption=f"Screenshot · {website_url or 'homepage'}", width=420)
        elif reveal == "colors" and branding.get("colors"):
            with colors_area.container():
                st.caption("Detected palette")
                render_color_swatches(branding["colors"])
        elif reveal == "logo" and logo:
            with logo_area.container():
                st.image(logo, width=90, caption="Logo")
    time.sleep(1.0)

    status2 = st.empty()
    bar2 = st.progress(0)
    insta_header_area = st.empty()
    insta_posts_area = st.empty()
    posts = insta.get("latestPosts", [])[:6]
    for pct, label, pause, reveal in [
        (15, f"📸 Connecting to Instagram {insta_handle or ''}...", 1.8, None),
        (35, "📸 Fetching profile info...", 1.8, "header"),
        (55, "📸 Pulling recent posts...", 0, "posts"),
        (75, "⬇️ Downloading media...", 1.6, None),
        (90, "🔖 Analyzing captions & hashtags...", 1.6, None),
        (100, "✅ Instagram scrape complete", 1.0, None),
    ]:
        status2.markdown(f"**{label}**")
        bar2.progress(pct)
        if reveal == "header" and insta:
            time.sleep(pause)
            with insta_header_area.container():
                render_instagram_header(insta, insta_handle)
        elif reveal == "posts" and posts:
            reveal_posts_progressively(insta_posts_area, posts)
        else:
            time.sleep(pause)
    time.sleep(1.0)

    final = st.empty()
    final.markdown("🧠 **Building business profile + brand kit from what we found...**")
    time.sleep(2.0)
    final.markdown("✅ **Business profile + brand kit ready.**")
    time.sleep(0.8)
    final.empty()
    status.empty()
    bar.empty()
    status2.empty()
    bar2.empty()

    return build_profile_from_scrape(website_url, insta_handle, website, insta)


def render_instagram_header(insta, insta_handle):
    h1, h2 = st.columns([1, 5])
    with h1:
        pic = fetch_image(insta.get("profilePicUrl"))
        if pic:
            st.image(pic, width=64)
    with h2:
        st.markdown(f"**@{insta.get('username', insta_handle)}** · "
                    f"{insta.get('followersCount', 0):,} followers")
        st.caption(insta.get("biography", ""))


def reveal_posts_progressively(area, posts, per_image_pause=0.4):
    shots = []
    for post in posts:
        shots.append(fetch_image(post.get("displayUrl")))
        with area.container():
            cols = st.columns(len(posts))
            for col, shot in zip(cols, shots):
                with col:
                    if shot:
                        st.image(shot, use_container_width=True)
        time.sleep(per_image_pause)


def render_instagram_preview(insta, insta_handle):
    render_instagram_header(insta, insta_handle)
    posts = insta.get("latestPosts", [])[:6]
    if posts:
        cols = st.columns(len(posts))
        for col, post in zip(cols, posts):
            with col:
                shot = fetch_image(post.get("displayUrl"))
                if shot:
                    st.image(shot, use_container_width=True)


def render_scrape_media(scraped):
    """Redraws the scraped website screenshot + Instagram preview so they stay
    visible across reruns (e.g. after clicking Save), not just during the animation."""
    if scraped.get("screenshot"):
        st.image(scraped["screenshot"],
                  caption=f"Screenshot · {scraped.get('website_url') or 'homepage'}", width=420)
    insta_list = load_json(INSTAGRAM_SCRAPE_PATH, [])
    insta = insta_list[0] if insta_list else {}
    if insta:
        render_instagram_preview(insta, scraped.get("insta_handle", ""))


def build_profile_from_scrape(website_url, insta_handle, website, insta):
    branding = website.get("branding", {})
    metadata = website.get("metadata", {})
    personality = branding.get("personality", {})
    colors = branding.get("colors", {})
    fonts = branding.get("typography", {}).get("fontFamilies", {})
    logo = branding.get("images", {}).get("logo") or branding.get("logo")

    brand_name = branding.get("brandName") or (metadata.get("title", "").split("|")[0].strip()) \
        or insta.get("fullName") or website_url or "Your Business"
    tone = personality.get("tone", "")
    energy = personality.get("energy", "")
    voice = (f"{tone.capitalize()} and {energy}-energy." if tone or energy
             else "Warm, friendly, on-brand.")
    biz_type = insta.get("businessCategoryName") or metadata.get("description", "")[:100] or "Small business"
    audience = personality.get("targetAudience") or "General audience"

    return {
        "brand_name": brand_name,
        "voice": voice,
        "constraints": "Stay on-brand with the detected color palette, fonts, and tone.",
        "biz_type": biz_type,
        "audience": audience,
        "goals": "Grow brand awareness and engagement",
        "website_url": website_url,
        "insta_handle": insta_handle,
        "summary": website.get("summary", ""),
        "bio": insta.get("biography", ""),
        "followers": insta.get("followersCount"),
        "screenshot": website.get("screenshot"),
        "logo": logo,
        "colors": colors,
        "fonts": fonts,
        "tone": tone,
        "energy": energy,
    }


def save_profile_to_memory(memory, user_id, profiles, scraped):
    """Writes the scraped profile to the local profile store and to Mem0,
    called right after the scrape animation finishes (no extra click needed)."""
    new = {"brand_name": scraped["brand_name"], "voice": scraped["voice"],
           "constraints": scraped["constraints"], "biz_type": scraped["biz_type"],
           "audience": scraped["audience"], "goals": scraped["goals"],
           "logo": scraped.get("logo"), "colors": scraped.get("colors"),
           "fonts": scraped.get("fonts"), "website_url": scraped.get("website_url"),
           "insta_handle": scraped.get("insta_handle")}
    profiles[user_id] = new
    save_json(PROFILE_PATH, profiles)
    memory.add(f"Brand: {new['brand_name']}. Voice: {new['voice']}. Rules: {new['constraints']}",
               {"kind": "brand", "section": "brand_info"}, infer=True)
    memory.add(f"Business: {new['biz_type']}. Audience: {new['audience']}. Goals: {new['goals']}",
               {"kind": "brand", "section": "business_info"}, infer=True)
    return new


def render_brand_kit(scraped):
    st.subheader("📇 Business profile")
    p1, p2 = st.columns(2)
    with p1:
        st.markdown(f"**Brand name:** {scraped['brand_name']}")
        st.markdown(f"**Business type:** {scraped['biz_type']}")
        st.markdown(f"**Audience:** {scraped['audience']}")
    with p2:
        st.markdown(f"**Voice:** {scraped['voice']}")
        if scraped.get("followers") is not None:
            st.markdown(f"**Instagram:** @{scraped.get('insta_handle', '')} · {scraped['followers']:,} followers")
    if scraped.get("summary"):
        st.caption(scraped["summary"])
    if scraped.get("bio"):
        st.caption(f"📸 \"{scraped['bio']}\"")

    st.subheader("🎨 Brand kit")
    k1, k2 = st.columns([1, 3])
    with k1:
        if scraped.get("logo"):
            st.image(scraped["logo"], width=100)
    with k2:
        render_color_swatches(scraped.get("colors") or {})
        fonts = scraped.get("fonts") or {}
        if fonts:
            st.caption("Fonts: " + ", ".join(f"{role}: {name}" for role, name in fonts.items()))


def run_round(memory, user_id, channel, brief, name, use_memory=True):
    """One full agent loop: recall -> plan -> simulate -> learn. Returns the saved campaign."""
    round_no = len([c for c in campaigns_for(user_id) if c["channel"] == channel]) + 1
    context = agent.recall(memory, channel, brief)
    p = agent.plan(memory, channel, use_memory, round_no)
    results = {k: agent.simulate(channel, p[k], f"{user_id}-{channel}-{round_no}-{k}") for k in ("A", "B")}
    outcome = agent.learn(memory, channel, p, results, name)
    primary = agent.CHANNELS[channel]["primary"]
    c = {
        "id": str(uuid.uuid4())[:8], "user_id": user_id, "name": name, "channel": channel,
        "brief": brief, "round": round_no, "plan": p, "results": results,
        "winner": outcome["winner"], "lift": outcome["lift"], "learning": outcome["learning"],
        "primary": primary, "winner_score": results[outcome["winner"]][primary],
        "memories_used": len(context["learnings"]), "use_memory": use_memory,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    save_campaign(c)
    return c, context


# ---------------- sidebar ----------------
with st.sidebar:
    st.title("🧪 A/B Marketing Agent")
    st.caption("Learns what works across campaigns with Mem0")
    user_id = st.text_input("Business ID", value="demo-coffee-co")
    memory = MemoryStore(user_id)
    st.markdown(f"**Memory backend:** {memory.backend}")
    if memory.last_error:
        st.warning(memory.last_error)
    page = st.radio("Go to", ["Dashboard", "New campaign", "Onboarding", "Memory"])
    st.divider()
    if st.button("Reset this business", type="secondary"):
        memory.reset()
        save_json(CAMPAIGNS_PATH, [c for c in load_json(CAMPAIGNS_PATH, []) if c["user_id"] != user_id])
        st.rerun()

profiles = load_json(PROFILE_PATH, {})
profile = profiles.get(user_id, {})
brand_name = profile.get("brand_name", user_id)

# ---------------- Onboarding ----------------
if page == "Onboarding":
    st.header("Onboarding")
    st.caption("Brand and business info are stored in Mem0 and recalled before every campaign.")

    st.subheader("🔎 Auto-fill from your website + Instagram")
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        website_url = st.text_input("Website URL", placeholder="https://yourbusiness.com")
    with c2:
        insta_handle = st.text_input("Instagram handle", placeholder="@yourbusiness")
    with c3:
        st.write("")
        st.write("")
        go = st.button("Go 🚀", type="primary", use_container_width=True)

    if go:
        scraped = run_scrape_animation(website_url, insta_handle)
        save_profile_to_memory(memory, user_id, profiles, scraped)
        st.session_state.scraped_profile = scraped
        st.rerun()

    scraped = st.session_state.get("scraped_profile")
    if scraped:
        with st.container(border=True):
            render_scrape_media(scraped)
            st.divider()
            render_brand_kit(scraped)
            st.success("Saved brand info + business info to memory.")

# ---------------- New campaign ----------------
elif page == "New campaign":
    st.header("New campaign")
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        brief = st.text_input("Campaign brief", value="Fall pumpkin spice cold brew launch")
    with c2:
        channel = st.selectbox("Channel", ["email", "instagram"])
    with c3:
        use_memory = st.toggle("Use memory", value=True)
    n = len([c for c in campaigns_for(user_id) if c["channel"] == channel]) + 1
    name = st.text_input("Campaign name", value=f"{channel.title()} #{n}: {brief}")

    if st.button("1 · Recall memory & generate A/B variants", type="primary"):
        context = agent.recall(memory, channel, brief)
        st.session_state.draft = {
            "context": context, "channel": channel, "brief": brief, "name": name,
            "use_memory": use_memory,
            "plan": agent.plan(memory, channel, use_memory, n),
            "llm_context": agent.build_llm_context(context, brief, channel),
        }
        st.session_state.pop("last_result", None)

    draft = st.session_state.get("draft")
    if draft and draft["channel"] == channel:
        ctx = draft["context"]
        with st.expander(f"🧠 Recalled from memory: {len(ctx['learnings'])} learnings, "
                         f"{len(ctx['brand'])} brand facts", expanded=True):
            if draft["use_memory"]:
                for m in ctx["learnings"][:6]:
                    st.markdown(f"- {m['memory']}")
                if not ctx["learnings"]:
                    st.caption("No learnings yet. This is the first test on this channel.")
            else:
                st.caption("Memory is OFF, so the agent ignores past learnings.")
            st.markdown("**Context that will be re-fed to the LLM (future):**")
            st.code(draft["llm_context"], language="text")

        p = draft["plan"]
        st.info(f"**Agent reasoning:** {p['reason']}")
        va, vb = st.columns(2)
        for col, key in ((va, "A"), (vb, "B")):
            with col, st.container(border=True):
                st.subheader(f"Variant {key}" + (" · champion" if key == "A" else " · challenger"))
                st.markdown(agent.render_copy(channel, p[key], draft["brief"], brand_name))
                st.caption(" · ".join(
                    f"**{k}={v}**" if k == p["tested_dimension"] else f"{k}={v}" for k, v in p[key].items()))

        if st.button("2 · Run A/B test (simulated audience) & write learning to memory"):
            c, _ = run_round(memory, user_id, channel, draft["brief"], draft["name"], draft["use_memory"])
            st.session_state.last_result = c
            st.session_state.pop("draft", None)
            st.rerun()

    res = st.session_state.get("last_result")
    if res:
        st.success(f"Variant {res['winner']} won (+{res['lift']:.0%} {res['primary']}). Learning saved to memory.")
        cols = st.columns(len(res["results"]["A"]))
        for col, metric in zip(cols, res["results"]["A"]):
            a, b = res["results"]["A"][metric], res["results"]["B"][metric]
            col.metric(f"{metric} (B vs A)", fmt(metric, b), f"{(b - a) / a:+.1%}")
        st.markdown(f"🧠 **Written to memory:** {res['learning']}")

# ---------------- Memory ----------------
elif page == "Memory":
    st.header("Agent memory")
    st.caption(f"Everything the agent remembers for `{user_id}` · backend: {memory.backend}")
    q = st.text_input("Search memory", placeholder="e.g. what subject lines work for email?")
    if q:
        for r in memory.search(q):
            st.markdown(f"- {r['memory']}  \n  <small>{r['source']} · {r['metadata']}</small>",
                        unsafe_allow_html=True)
    items = memory.all()
    if items:
        df = pd.DataFrame([{"kind": m["metadata"].get("kind"), "channel": m["metadata"].get("channel", ""),
                            "memory": m["memory"], "mem0": "✅" if m["synced_to_mem0"] else "local",
                            "created": m["created_at"]} for m in reversed(items)])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No memories yet. Start with Onboarding.")

# ---------------- Dashboard ----------------
else:
    st.header(f"Dashboard · {brand_name}")
    camps = campaigns_for(user_id)
    learnings = memory.all(kind="learning")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Campaigns run", len(camps))
    k2.metric("Memories stored", len(memory.all()))
    for col, ch in ((k3, "email"), (k4, "instagram")):
        ch_c = [c for c in camps if c["channel"] == ch]
        primary = agent.CHANNELS[ch]["primary"]
        if ch_c:
            first, last = ch_c[0]["winner_score"], ch_c[-1]["winner_score"]
            col.metric(f"{ch.title()} {primary}", f"{last:.2%}", f"{(last - first) / first:+.0%} since campaign 1")
        else:
            col.metric(f"{ch.title()} {primary}", "-")

    with st.container(border=True):
        st.markdown("**Quick demo:** run several campaign rounds automatically")
        d1, d2, d3, d4 = st.columns([1, 1, 2, 1])
        auto_ch = d1.selectbox("Channel", ["email", "instagram"], key="auto_ch")
        auto_n = d2.number_input("Rounds", 1, 10, 5)
        auto_brief = d3.text_input("Brief", "Fall pumpkin spice cold brew launch", key="auto_brief")
        if d4.button("Run rounds", type="primary"):
            for _ in range(int(auto_n)):
                k = len([c for c in campaigns_for(user_id) if c["channel"] == auto_ch]) + 1
                run_round(memory, user_id, auto_ch, auto_brief, f"{auto_ch.title()} #{k}")
            st.rerun()

    if not camps:
        st.info("No campaigns yet. Create one under **New campaign** or use Quick demo above.")
    else:
        left, right = st.columns([3, 2])
        with left:
            st.subheader("Performance across campaigns")
            for ch in ("email", "instagram"):
                ch_c = [c for c in camps if c["channel"] == ch]
                if not ch_c:
                    continue
                primary = agent.CHANNELS[ch]["primary"]
                df = pd.DataFrame({"campaign": [c["round"] for c in ch_c],
                                   f"winner {primary}": [c["winner_score"] for c in ch_c],
                                   "variant A": [c["results"]["A"][primary] for c in ch_c],
                                   "variant B": [c["results"]["B"][primary] for c in ch_c]}).set_index("campaign")
                st.markdown(f"**{ch.title()}: {primary} by campaign**")
                st.line_chart(df)
        with right:
            st.subheader("🧠 What the agent learned")
            for m in reversed(learnings[-8:]):
                md = m["metadata"]
                st.markdown(f"- **{md['channel']} / {md['dimension']}**: `{md['winner']}` > `{md['loser']}` "
                            f"(+{md['lift']:.0%})")
            pbs = memory.all(kind="playbook")
            for ch in ("email", "instagram"):
                latest = [m for m in pbs if m["metadata"].get("channel") == ch]
                if latest:
                    st.markdown(f"**Current {ch} playbook**")
                    st.json(latest[-1]["metadata"]["config"], expanded=False)

        st.subheader("Campaigns")
        cols = st.columns(3)
        for i, c in enumerate(reversed(camps)):
            with cols[i % 3], st.container(border=True):
                st.markdown(f"**{c['name']}**")
                st.caption(f"{c['channel']} · round {c['round']} · tested `{c['plan']['tested_dimension']}` · "
                           f"{c['memories_used']} memories used")
                st.metric(f"Winner {c['winner']} {c['primary']}", fmt(c["primary"], c["winner_score"]),
                          f"+{c['lift']:.0%} vs loser")

        st.subheader("Memory ON vs OFF")
        st.caption("Same simulated audience. Without memory the agent keeps restarting from generic "
                   "best practices; with memory it compounds wins.")
        bench_ch = st.selectbox("Benchmark channel", ["email", "instagram"], key="bench")
        if st.button("Run 8-round benchmark"):
            rows = []
            for mode, use in (("Memory ON", True), ("Memory OFF", False)):
                bm = MemoryStore(f"{user_id}__bench_{mode.split()[1].lower()}")
                bm.client = None  # keep the benchmark local and fast
                bm.reset()
                primary = agent.CHANNELS[bench_ch]["primary"]
                for r in range(1, 9):
                    p = agent.plan(bm, bench_ch, use, r)
                    res = {k: agent.simulate(bench_ch, p[k], f"bench-{bench_ch}-{r}-{k}-{mode}") for k in "AB"}
                    if use:
                        agent.learn(bm, bench_ch, p, res, f"bench {r}")
                    rows.append({"round": r, "mode": mode, primary: max(res["A"][primary], res["B"][primary])})
                bm.reset()
            bdf = pd.DataFrame(rows).pivot(index="round", columns="mode", values=primary)
            st.line_chart(bdf)
