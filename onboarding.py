"""Onboarding: simulated website + Instagram scrape -> business profile + brand kit.

The scrape is canned fixtures in data/business-onboarding/ (no live scraping),
timed to feel live.
"""
import time

import requests
import streamlit as st

from campaigns import PROFILE_PATH, load_json, save_json
from memory_store import DATA_DIR

ONBOARD_DIR = DATA_DIR / "business-onboarding"
WEBSITE_SCRAPE_PATH = ONBOARD_DIR / "website.json"
INSTAGRAM_SCRAPE_PATH = ONBOARD_DIR / "instagram.json"


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
                        st.image(shot, width="stretch")
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
                    st.image(shot, width="stretch")


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
           "insta_handle": scraped.get("insta_handle"), "summary": scraped.get("summary"),
           "bio": scraped.get("bio"), "followers": scraped.get("followers"),
           "screenshot": scraped.get("screenshot")}
    profiles[user_id] = new
    save_json(PROFILE_PATH, profiles)
    memory.add(f"Brand: {new['brand_name']}. Voice: {new['voice']}. Rules: {new['constraints']}",
               {"kind": "brand", "section": "brand_info"}, infer=True)
    memory.add(f"Business: {new['biz_type']}. Audience: {new['audience']}. Goals: {new['goals']}",
               {"kind": "brand", "section": "business_info"}, infer=True)
    return new


def render_brand_kit(scraped):
    st.subheader("Business profile")
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
        st.caption(f"Instagram bio: \"{scraped['bio']}\"")

    st.subheader("Brand kit")
    k1, k2 = st.columns([1, 3])
    with k1:
        if scraped.get("logo"):
            st.image(scraped["logo"], width=100)
    with k2:
        render_color_swatches(scraped.get("colors") or {})
        fonts = scraped.get("fonts") or {}
        if fonts:
            st.caption("Fonts: " + ", ".join(f"{role}: {name}" for role, name in fonts.items()))
