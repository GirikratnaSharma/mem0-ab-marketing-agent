"""Streamlit dashboard for the Mem0 A/B marketing agent."""
import json
import uuid
from datetime import datetime

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

import agent
import llm
from memory_store import DATA_DIR, MemoryStore

load_dotenv()
st.set_page_config(page_title="A/B Marketing Agent · Mem0", page_icon="🧪", layout="wide")

CAMPAIGNS_PATH = DATA_DIR / "campaigns.json"
PROFILE_PATH = DATA_DIR / "profiles.json"


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
    with st.form("onboarding"):
        c1, c2 = st.columns(2)
        with c1:
            bn = st.text_input("Brand name", value=profile.get("brand_name", "Bean There Coffee"))
            voice = st.text_area("Brand voice", value=profile.get("voice", "Warm, playful, never pushy. No ALL CAPS."))
            constraints = st.text_area("Rules / constraints", value=profile.get("constraints", "Max discount 15%. No competitor mentions."))
        with c2:
            biz_type = st.text_input("Business type", value=profile.get("biz_type", "Neighborhood coffee shop + online bean subscriptions"))
            audience = st.text_area("Target audience", value=profile.get("audience", "Young professionals 22-35 in SF, remote workers"))
            goals = st.text_area("Marketing goals", value=profile.get("goals", "Grow subscriptions, bring lapsed customers back"))
        submitted = st.form_submit_button("Save to memory", type="primary")
    if submitted:
        new = {"brand_name": bn, "voice": voice, "constraints": constraints,
               "biz_type": biz_type, "audience": audience, "goals": goals}
        profiles[user_id] = new
        save_json(PROFILE_PATH, profiles)
        memory.add(f"Brand: {bn}. Voice: {voice}. Rules: {constraints}",
                   {"kind": "brand", "section": "brand_info"}, infer=True)
        memory.add(f"Business: {biz_type}. Audience: {audience}. Goals: {goals}",
                   {"kind": "brand", "section": "business_info"}, infer=True)
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
        draft = st.session_state.draft
        draft["copy"], draft["copy_note"] = None, "Rule-based copy (set OLLAMA_MODEL, KIMI_API_KEY or ANTHROPIC_API_KEY)."
        if llm.available():
            try:
                with st.spinner(f"{llm.provider()} is writing the variants from memory..."):
                    draft["copy"] = llm.write_variants(channel, draft["plan"], draft["llm_context"], brand_name)
                draft["copy_note"] = f"✍️ Written by {llm.provider()}: {draft['copy']['rationale']}"
            except Exception as e:  # keep the demo alive
                draft["copy_note"] = f"{llm.provider()} call failed, using rule-based copy: {e}"
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
            st.markdown("**Context fed to the LLM:**")
            st.code(draft["llm_context"], language="text")

        p = draft["plan"]
        st.info(f"**Agent reasoning:** {p['reason']}")
        st.caption(draft.get("copy_note", ""))
        va, vb = st.columns(2)
        for col, key in ((va, "A"), (vb, "B")):
            with col, st.container(border=True):
                st.subheader(f"Variant {key}" + (" · champion" if key == "A" else " · challenger"))
                copy = draft.get("copy")
                st.markdown(copy[key] if copy else agent.render_copy(channel, p[key], draft["brief"], brand_name))
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
