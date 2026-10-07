"""Streamlit app for the Mem0 A/B marketing agent."""
import html

import altair as alt
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

import agent  # noqa: E402
import onboarding  # noqa: E402
import strategist  # noqa: E402
import ui  # noqa: E402
from campaigns import (PROFILE_PATH, campaigns_for, clear_drafts, delete_campaigns, load_draft,  # noqa: E402
                       load_json, next_round, run_round, save_draft, save_json)
from memory_store import MemoryStore  # noqa: E402

st.set_page_config(page_title="Campaign Lab", page_icon=":material/science:", layout="wide")
ui.inject_css()

DEFAULT_BRIEF = "Fall session enrollment: free trial class for new students"
CHANNEL_LABELS = {"email": ":material/mail: Email", "instagram": ":material/photo_camera: Instagram"}
CHANNEL_NAMES = {"email": "email", "instagram": "Instagram"}
SIM_NOTE = "Simulated audience: nothing is sent to your customers."
INK, MUTED, ACCENT = "#1C1A17", "#B9AFA1", "#C99A00"

# ---------------- workspace ----------------
if "user_id" not in st.session_state:
    st.session_state.user_id = "kung-fu-kids"
user_id = st.session_state.user_id
memory = MemoryStore(user_id)
profiles = load_json(PROFILE_PATH, {})
profile = profiles.get(user_id, {})
brand_name = profile.get("brand_name") or user_id.replace("-", " ").title()
llm_ok, llm_label = st.cache_data(ttl=600, show_spinner=False)(strategist.llm_status)()


def clear_flow():
    clear_drafts(user_id)
    st.session_state.pop("last_result", None)


def sidebar():
    with st.sidebar:
        logo = profile.get("logo")
        img = (f'<img src="{html.escape(logo)}" alt="{html.escape(brand_name)} logo" width="44" height="44" '
               f'style="border-radius:50%;background:#fff;border:1px solid #E4DCCF">') if logo else ""
        st.markdown(f'<div style="display:flex;gap:12px;align-items:center">{img}<div>'
                    f'<b>{html.escape(brand_name)}</b><br><span class="muted">Campaign Lab</span></div></div>',
                    unsafe_allow_html=True)
        st.markdown(ui.tag("Memory: Mem0" if memory.client else "Memory: on this computer",
                           "ok" if memory.client else "")
                    + ui.tag("AI writer: on" if llm_ok else "AI writer: offline", "ok" if llm_ok else "warn"),
                    unsafe_allow_html=True)
        st.divider()
        with st.expander("Workspace", icon=":material/settings:"):
            new_id = st.text_input("Business ID", value=user_id,
                                   help="Each business has its own memory and test history.")
            if new_id.strip() and new_id != user_id:
                st.session_state.user_id = new_id.strip()
                st.session_state.pop("last_result", None)
                st.rerun()
            st.caption(f"AI writer: {llm_label}")
            if st.session_state.get("llm_error"):
                st.caption(f"Last AI error: {st.session_state.llm_error}")
            if memory.last_error:
                st.caption(f"Memory error: {memory.last_error}")
            if st.button("Reset this business", type="secondary", width="stretch",
                         help="Deletes this business's tests, brand and memories."):
                memory.reset()
                delete_campaigns(user_id)
                clear_flow()
                profiles.pop(user_id, None)
                save_json(PROFILE_PATH, profiles)
                st.rerun()


def go(page):
    st.switch_page(PAGES[page])


def load_sample_data():
    """A filled-in demo: the Kung Fu Kids brand plus simulated email and Instagram history."""
    with st.spinner("Loading the sample business and running simulated tests..."):
        if not profile:
            w = load_json(onboarding.WEBSITE_SCRAPE_PATH, {}).get("data", {})
            ig = (load_json(onboarding.INSTAGRAM_SCRAPE_PATH, []) or [{}])[0]
            onboarding.save_profile_to_memory(memory, user_id, profiles, onboarding.build_profile_from_scrape(
                "https://kungfukids.com", "@wushucentral", w, ig))
        for channel, n in (("email", 5), ("instagram", 3)):
            for _ in range(n):
                run_round(memory, user_id, channel, DEFAULT_BRIEF,
                          f"{channel.title()} #{next_round(user_id, channel)}: {agent.short_topic(DEFAULT_BRIEF)}")
    st.toast("Sample data loaded", icon=":material/check:")


# ---------------- Home ----------------
def home_page():
    camps = campaigns_for(user_id)
    steps = [
        ("brand", "Set up your brand",
         "Import your website and Instagram so every version sounds like you. Takes about 30 seconds.",
         bool(profile), "Set up your brand"),
        ("create", "Run your first test",
         "Describe what you're promoting. Campaign Lab suggests one change, writes versions A and B, "
         "and scores them with a simulated audience.", len(camps) >= 1, "Run your first test"),
        ("create", "Run a follow-up test",
         "Version A now starts from the winner. Test one more idea and watch the playbook grow.",
         len(camps) >= 2, "Run a follow-up test"),
    ]
    if all(done for *_, done, _ in steps):
        return home_returning(camps)

    ui.page_header("Welcome to Campaign Lab",
                   "Test one idea at a time, keep what wins, and let every email and Instagram post "
                   "start from what worked last time.")
    st.markdown('<p class="lede">Three steps to your first lesson.</p>', unsafe_allow_html=True)
    current = next(i for i, (*_, done, _) in enumerate(steps) if not done)
    st.markdown('<div class="journey"></div>', unsafe_allow_html=True)
    for i, (page, title, desc, done, cta) in enumerate(steps):
        state = "done" if done else "current" if i == current else "later"
        left, right = st.columns([5, 1.6], vertical_alignment="center")
        with left:
            ui.journey_step(i + 1, title, desc, state)
        if state == "current":
            if right.button(cta, type="primary", icon=":material/arrow_forward:", width="stretch", key=f"j{i}"):
                go(page)
        elif state == "done" and page == "brand":
            if right.button("View brand", key=f"j{i}", width="stretch"):
                go(page)
        st.markdown('<div class="jrule"></div>', unsafe_allow_html=True)

    st.write("")
    with st.container(border=True):
        c1, c2 = st.columns([5, 1.6], vertical_alignment="center")
        c1.markdown("**Just looking around?** Load a sample business (Kung Fu Kids) with 8 simulated tests "
                    "to see a full history. You can clear it later in Workspace.")
        if c2.button("Load sample data", icon=":material/dataset:", width="stretch"):
            load_sample_data()
            st.rerun()


def home_returning(camps):
    ui.page_header(f"Welcome back, {brand_name}", "Here's where you left off.")
    learnings = memory.all(kind="learning")
    last = camps[-1]
    with st.container(border=True):
        st.markdown(f'<p class="lede">Your next test starts from {len(learnings)} '
                    f'lesson{"s" if len(learnings) != 1 else ""}.</p>'
                    f'<div class="muted" style="margin-bottom:6px">Last result · {ui.esc(last["name"])}: '
                    f'{ui.esc(result_phrase(last))}.</div>', unsafe_allow_html=True)
        for ch in ("email", "instagram"):
            if any(m["metadata"].get("channel") == ch for m in learnings):
                ui.playbook_strip(learnings, ch)
        b1, b2, b3, _ = st.columns([1.3, 1.1, 1.1, 2])
        if b1.button("Run your next test", type="primary", icon=":material/science:", width="stretch"):
            go("create")
        if b2.button("See results", icon=":material/insights:", width="stretch"):
            go("results")
        if b3.button("View last result", icon=":material/history:", width="stretch"):
            st.session_state.last_result = last
            go("create")
    st.write("")
    with st.expander("How Campaign Lab works", icon=":material/help:"):
        st.markdown(
            "1. **Your brand** is saved to memory so every version sounds like you.\n"
            "2. **Each test** keeps what already won (version A) and changes one thing (version B).\n"
            "3. **A simulated audience** scores both. Nothing is sent to real customers yet.\n"
            "4. **The lesson is saved**, and the next test starts from the winner. That's the playbook.")


# ---------------- Results ----------------
def performance_chart(camps, channel):
    primary = agent.CHANNELS[channel]["primary"]
    rows = []
    for c in camps:
        rows += [{"test": c["round"], "series": "Best of the two", "value": c["winner_score"], "name": c["name"]},
                 {"test": c["round"], "series": "A", "value": c["results"]["A"][primary], "name": c["name"]},
                 {"test": c["round"], "series": "B", "value": c["results"]["B"][primary], "name": c["name"]}]
    color = alt.Color("series:N", scale=alt.Scale(domain=["Best of the two", "A", "B"], range=[INK, MUTED, ACCENT]),
                      legend=alt.Legend(orient="top", title=None))
    base = alt.Chart(pd.DataFrame(rows)).encode(
        x=alt.X("test:O", title="Test #", axis=alt.Axis(labelAngle=0)),
        y=alt.Y("value:Q", title=ui.metric_label(primary), axis=alt.Axis(format="%")),
        color=color, tooltip=["name", "series", alt.Tooltip("value:Q", format=".2%")])
    chart = (base.mark_line(strokeWidth=2.5).transform_filter("datum.series == 'Best of the two'")
             + base.mark_point(filled=True, size=55))
    st.altair_chart(style_chart(chart), width="stretch")


def style_chart(chart):
    return (chart.properties(height=260)
            .configure_axis(gridColor="#E4DCCF", domainColor="#CFC5B5", tickColor="#CFC5B5",
                            labelColor="#4F4941", titleColor="#4F4941", labelFontSize=12, titleFontSize=12)
            .configure_legend(labelColor="#1C1A17", labelFontSize=12)
            .configure_view(stroke=None))


def results_page():
    ui.page_header("Results", "Step 3 of 3 · How your tests went and what Campaign Lab learned. "
                              "Results come from a simulated audience.")
    camps = campaigns_for(user_id)
    learnings = memory.all(kind="learning")

    k = st.columns(4)
    k[0].metric("Tests run", len(camps), border=True, height="stretch")
    k[1].metric("Lessons in memory", len(learnings), border=True, height="stretch")
    for col, ch in ((k[2], "email"), (k[3], "instagram")):
        ch_c = [c for c in camps if c["channel"] == ch]
        title = f"{ch.title()} {ui.metric_label(agent.CHANNELS[ch]['primary']).lower()}"
        if ch_c:
            first, last = ch_c[0]["winner_score"], ch_c[-1]["winner_score"]
            col.metric(title, f"{last:.2%}", f"{(last - first) / first:+.0%} since test 1",
                       chart_data=[c["winner_score"] for c in ch_c], chart_type="line", border=True,
                       height="stretch")
        else:
            col.metric(title, "—", "no tests yet", delta_color="off", border=True, height="stretch")

    if not camps:
        st.markdown('<div class="empty"><h2 style="font-size:1.4rem;margin:0 0 6px">No results yet</h2>'
                    '<p class="muted" style="margin:0">Results appear here after your first test.</p></div>',
                    unsafe_allow_html=True)
        st.write("")
        if st.button("Run your first test", type="primary", icon=":material/science:"):
            go("create")
    else:
        if st.button("Run your next test", type="primary", icon=":material/science:"):
            go("create")
        left, right = st.columns([3, 2], gap="large")
        with left, st.container(border=True):
            st.markdown("**Results by test**")
            channels = [ch for ch in ("email", "instagram") if any(c["channel"] == ch for c in camps)]
            ch = st.segmented_control("Channel", channels, default=channels[0], key="perf_ch",
                                      format_func=CHANNEL_LABELS.get, label_visibility="collapsed") or channels[0]
            performance_chart([c for c in camps if c["channel"] == ch], ch)
        with right, st.container(border=True):
            st.markdown("**What Campaign Lab has learned**")
            ui.lessons(learnings, limit=7)

        st.header("Test history", anchor=False)
        df = pd.DataFrame([{
            "Test": c["name"], "Channel": c["channel"].title(),
            "Tested": agent.DIMENSION_LABELS.get(c["plan"]["tested_dimension"], c["plan"]["tested_dimension"]),
            "Result": ("Too close to call" if c.get("tie") else
                       agent._cap(agent.option_label(c["channel"], c["plan"]["tested_dimension"],
                                                     c["plan"][c["winner"]][c["plan"]["tested_dimension"]])) + " won"),
            "Difference": c["lift"], "Best result": c["winner_score"],
            "Planned by": {"claude": "Claude", "openrouter": "AI writer (OpenRouter)",
                           "offline": "Built-in strategist"}.get(c.get("strategy_source"), "Autopilot"),
            "Date": c["created_at"][:10]} for c in reversed(camps)])
        st.dataframe(df, hide_index=True, width="stretch", column_config={
            "Difference": st.column_config.NumberColumn(format="percent"),
            "Best result": st.column_config.NumberColumn(format="percent")})

    with st.expander("Add simulated history", icon=":material/fast_forward:"):
        st.caption("Runs simulated tests on autopilot (no AI writer) so you can watch learning add up.")
        d1, d2, d3, d4 = st.columns([1, 1, 2, 1], vertical_alignment="bottom")
        auto_ch = d1.selectbox("Channel", ["email", "instagram"], key="auto_ch", format_func=CHANNEL_LABELS.get)
        auto_n = d2.number_input("Tests", 1, 10, 5)
        auto_brief = d3.text_input("Brief", DEFAULT_BRIEF, key="auto_brief")
        if d4.button("Run tests", type="primary", width="stretch"):
            with st.spinner("Running simulated tests..."):
                for _ in range(int(auto_n)):
                    n = next_round(user_id, auto_ch)
                    run_round(memory, user_id, auto_ch, auto_brief, f"{auto_ch.title()} #{n}")
            st.rerun()

    with st.expander("Why memory matters: with vs without memory", icon=":material/compare_arrows:"):
        st.caption("Same simulated audience, 8 tests each. Without memory the agent restarts from "
                   "generic best practice every time; with memory, wins add up.")
        b1, b2 = st.columns([1, 3], vertical_alignment="bottom")
        bench_ch = b1.selectbox("Channel", ["email", "instagram"], key="bench", format_func=CHANNEL_LABELS.get)
        if b2.button("Run comparison"):
            rows = []
            primary = agent.CHANNELS[bench_ch]["primary"]
            for mode, use in (("With memory", True), ("Without memory", False)):
                bm = MemoryStore(f"{user_id}__bench_{'on' if use else 'off'}")
                bm.client = None  # keep the benchmark local and fast
                bm.reset()
                for r in range(1, 9):
                    p = agent.plan(bm, bench_ch, use, r)
                    res = {k: agent.simulate(bench_ch, p[k], f"bench-{bench_ch}-{r}-{k}-{mode}") for k in "AB"}
                    if use:
                        agent.learn(bm, bench_ch, p, res, f"bench {r}")
                    rows.append({"test": r, "mode": mode, "value": max(res["A"][primary], res["B"][primary])})
                bm.reset()
            chart = alt.Chart(pd.DataFrame(rows)).mark_line(point=True, strokeWidth=2.5).encode(
                x=alt.X("test:O", title="Test #", axis=alt.Axis(labelAngle=0)),
                y=alt.Y("value:Q", title=ui.metric_label(primary), axis=alt.Axis(format="%")),
                color=alt.Color("mode:N", scale=alt.Scale(domain=["With memory", "Without memory"],
                                                          range=[INK, MUTED]),
                                legend=alt.Legend(orient="top", title=None)))
            st.altair_chart(style_chart(chart), width="stretch")


# ---------------- Create campaign ----------------
def auto_name(channel, brief):
    return f"{channel.title()} #{next_round(user_id, channel)}: {agent.short_topic(brief)}"


def generate(brief, channel, use_memory, custom_name="", avoid=(), force=None, edits=None):
    camps = campaigns_for(user_id)
    n_past = len([m for m in memory.all(kind="learning") if m["metadata"].get("channel") == channel])
    with st.status("Planning your test...", expanded=True) as status:
        st.write(f"Reading your {n_past} past {CHANNEL_NAMES[channel]} test{'s' if n_past != 1 else ''}"
                 if use_memory and n_past else "No past tests on this channel yet: starting from best practice")
        st.write("Writing both versions" + (" with the AI writer (about 20–30 seconds)" if llm_ok else ""))
        out = strategist.suggest(memory, channel, brief, profile, camps, use_memory,
                                 next_round(user_id, channel), avoid, force)
        status.update(label="Your test is ready", state="complete", expanded=False)
    if out["error"]:
        st.session_state.llm_error = out["error"]
    save_draft(user_id, channel, {**out, "brief": brief, "channel": channel, "use_memory": use_memory,
                                  "custom_name": custom_name, "name": custom_name or auto_name(channel, brief)})
    st.session_state.pop("last_result", None)
    st.rerun()


def what_changed(draft, brief, use_memory):
    if draft["brief"] != brief:
        return "You edited the brief since this suggestion."
    return f"You turned past results {'on' if use_memory else 'off'} since this suggestion."


def last_result_line():
    camps = campaigns_for(user_id)
    if not camps:
        return
    c = camps[-1]
    left, right = st.columns([4, 1], vertical_alignment="center")
    left.markdown(f'<span class="muted">Last result · {ui.esc(c["name"])}: '
                  f'{ui.esc(result_phrase(c))}</span>', unsafe_allow_html=True)
    if right.button("View", key="view_last", icon=":material/history:", width="stretch"):
        st.session_state.last_result = c
        st.rerun()


def result_phrase(c):
    dim = c["plan"]["tested_dimension"]
    if c.get("tie"):
        return "too close to call"
    return agent.option_label(c["channel"], dim, c["plan"][c["winner"]][dim]) + " won"


def create_page():
    ui.page_header("Run a test", "Step 2 of 3 · Describe what you're promoting. Campaign Lab suggests "
                                 "one change to test, using what worked before.")
    if not profile:
        with st.container(border=True):
            c1, c2 = st.columns([5, 1.4], vertical_alignment="center")
            c1.markdown("**Your brand isn't set up yet.** You can still run a test, but the versions "
                        "won't use your name, voice, logo or colors.")
            if c2.button("Set up brand", icon=":material/palette:", width="stretch"):
                go("brand")
    res = st.session_state.get("last_result")
    if res and res["user_id"] != user_id:
        res = None
    if "channel" not in st.session_state:
        st.session_state.channel = res["channel"] if res else "email"
    channel = st.session_state.channel
    draft = load_draft(user_id, channel)

    # ---- step 1: brief ----
    step1 = st.empty()
    with st.container(border=True):
        c1, c2 = st.columns([3, 1], gap="medium")
        brief = c1.text_area("What are you promoting?", value=draft["brief"] if draft else DEFAULT_BRIEF,
                             height=88, max_chars=280,
                             placeholder="e.g. Back-to-school special: two free trial classes in September")
        channel = c2.segmented_control("Channel", ["email", "instagram"], key="channel",
                                       format_func=CHANNEL_LABELS.get) or "email"
        draft = load_draft(user_id, channel)
        use_memory = c2.toggle("Use past results", value=draft["use_memory"] if draft else True,
                               help="On: version A starts from what already won. Off: from common best practice.")
        with c2.popover("Test name", icon=":material/edit:", width="stretch"):
            name = st.text_input("Test name (optional)", value=(draft or {}).get("custom_name", ""),
                                 max_chars=60, placeholder=auto_name(channel, brief))
        ui.playbook_strip(memory.all(kind="learning") if use_memory else [], channel)

        brief = brief.strip()
        stale = bool(draft) and not res and (draft["brief"] != brief or draft["use_memory"] != use_memory)
        if res:
            pass  # the results below own the next action ("Plan the next test")
        elif not draft:
            if st.button("Suggest a test", type="primary", icon=":material/science:", disabled=not brief):
                generate(brief, channel, use_memory, name.strip())
            if not brief:
                st.caption("Add what you're promoting to get a suggestion.")
            last_result_line()
        elif stale:
            st.markdown(ui.tag("Changed") + f'<span class="muted">{what_changed(draft, brief, use_memory)} '
                        'Undo the change to see it again, or get a new one.</span>', unsafe_allow_html=True)
            if st.button("Get a new suggestion", type="primary", icon=":material/refresh:", disabled=not brief):
                generate(brief, channel, use_memory, name.strip())
    state1 = "active" if (not draft or stale) and not res else "done"
    with step1:
        ui.step(1, "Brief", "What you're promoting, and where", state1)

    if res:
        ui.step(2, "The test", strategy_line(res), "done")
        render_results(res)
    elif draft and not stale:
        if name.strip() != draft.get("custom_name", ""):  # renaming doesn't invalidate the plan
            draft["custom_name"] = name.strip()
            draft["name"] = name.strip() or auto_name(channel, draft["brief"])
            save_draft(user_id, channel, draft)
        render_test(draft)
    else:
        ui.step(2, "The test", "Two versions that differ in one thing", "todo")
        ui.step(3, "Results", "Which version won, and what gets remembered", "todo")


def strategy_line(c):
    dim = c["plan"]["tested_dimension"]
    return agent.describe_change(c["channel"], dim, c["plan"]["A"][dim], c["plan"]["B"][dim])


def render_test(draft):
    s, p, ch = draft["strategy"], draft["plan"], draft["channel"]
    dim = p["tested_dimension"]
    ui.step(2, "The test", f"Two {CHANNEL_NAMES[ch]} versions that differ only in the {agent.DIMENSION_LABELS[dim]}")
    ui.test_statement(s, ch, draft["source"], draft.get("n_tests", 0), draft.get("error"))

    t1, t2, _ = st.columns([1, 1, 2.2])
    options = [tuple(o) for o in draft.get("options", [])]
    with t1.popover("Choose the change", icon=":material/tune:", width="stretch"):
        st.caption("Pick what version B changes. Version A stays as it is.")
        pick = st.selectbox("Test", options, index=None, placeholder="Choose a change",
                            format_func=lambda o: agent.describe_change(ch, o[0], p["A"][o[0]], o[1]),
                            label_visibility="collapsed")
        if st.button("Use this test", type="primary", disabled=pick is None, width="stretch"):
            generate(draft["brief"], ch, draft["use_memory"], draft.get("custom_name", ""), force=pick)
        if draft.get("locks"):
            st.caption("Kept from your brief: " + ", ".join(
                agent.option_label(ch, d, v) for d, v in draft["locks"].items()) + ".")
    plan_id = f"{ch}-{dim}-{p['B'][dim]}-{len(draft.get('suggested', []))}"
    with t2.popover("Edit wording", icon=":material/edit_note:", width="stretch"):
        st.caption("Fix any wording. Keep the difference between A and B to the one change, "
                   "so the result stays easy to read.")
        edited = {}
        for key, col in zip(("variant_a", "variant_b"), st.columns(2)):
            with col:
                st.markdown(f"**Version {key[-1].upper()}**")
                edited[key] = {f: col.text_area(lbl, s[key][f], key=f"edit_{key}_{f}_{plan_id}",
                                                height=68 if f != "body" else 120)
                               for f, lbl in (("headline", "Subject line" if ch == "email" else "First line"),
                                              ("body", "Body" if ch == "email" else "Caption"),
                                              ("cta", "Button" if ch == "email" else "Call to action"))}
        if st.button("Save wording", type="primary", width="stretch"):
            for key in edited:
                s[key].update(edited[key])
            save_draft(user_id, ch, draft)
            st.rerun()

    diff = agent.option_label(ch, dim, p["B"][dim])
    st.markdown(f'<div class="diffline"><b>Only difference:</b> version B uses {ui.esc(diff)}.</div>',
                unsafe_allow_html=True)
    va, vb = st.columns(2, gap="large")
    for col, key, copy, other in ((va, "A", s["variant_a"], s["variant_b"]), (vb, "B", s["variant_b"], s["variant_a"])):
        with col:
            desc = "What's working now" if key == "A" else f"One change: {diff}"
            st.markdown(f'<div class="vlabel"><span class="vletter">{key}</span>'
                        f'<span class="vdesc">{ui.esc(desc)}</span></div>', unsafe_allow_html=True)
            ui.variant_preview(ch, copy, other, p[key], dim, key, brand_name, profile)

    st.write("")
    ui.why_section(s)
    past = draft["past"]
    if past:
        with st.expander(f"Past tests with a similar brief ({len(past)})", icon=":material/history:"):
            st.dataframe(pd.DataFrame([{"Test": c["name"], "Result": agent._cap(result_phrase(c)),
                                        "Difference": f"{c['lift']:.0%}"} for c in past]),
                         hide_index=True, width="stretch")
    if st.query_params.get("debug"):
        with st.expander("Debug: context sent to the strategist"):
            st.code(draft["prompt"], language="text")

    with st.container(key="runbar"):
        b1, b2, b3 = st.columns([1.3, 1.3, 3], vertical_alignment="center")
        if b1.button("Run simulated test", type="primary", icon=":material/play_arrow:", width="stretch"):
            with st.spinner("Scoring both versions with a simulated audience..."):
                c = run_round(memory, user_id, ch, draft["brief"], draft["name"], draft["use_memory"],
                              plan=p, strategy=s, source=draft["source"],
                              memories_used=len(draft["context"]["learnings"]))
            st.session_state.last_result = c
            save_draft(user_id, ch, None)
            st.rerun()
        if b2.button("Suggest another", icon=":material/refresh:", width="stretch",
                     help="Picks a different change to test for the same brief."):
            generate(draft["brief"], ch, draft["use_memory"], draft.get("custom_name", ""),
                     draft.get("suggested", []))
        b3.markdown(f'<span class="muted"><span class="only-desktop">{SIM_NOTE}</span>'
                    '<span class="only-mobile">Simulated. Nothing is sent.</span></span>', unsafe_allow_html=True)


SCORING_HELP = ("A simulated audience with hidden tastes reacts to both versions; Campaign Lab has to "
                "discover those tastes one test at a time. Nothing is sent to real people. When the two "
                f"versions land within {agent.TIE_LIFT:.0%} of each other, that gap could be chance, so it's "
                "called too close to call and nothing changes in your playbook.")


def render_results(res):
    ch, dim = res["channel"], res["plan"]["tested_dimension"]
    a_txt = agent.option_label(ch, dim, res["plan"]["A"][dim])
    b_txt = agent.option_label(ch, dim, res["plan"]["B"][dim])
    metric = ui.metric_label(res["primary"]).lower()
    a, b = res["results"]["A"][res["primary"]], res["results"]["B"][res["primary"]]
    diff = (b - a) / a if a else 0  # same number as the "B vs A" column
    ui.step(3, "Results", res["name"])
    if res.get("tie"):
        verdict = "Too close to call."
        sub = (f"{agent._cap(b_txt)} and {a_txt} landed within {abs(diff):.1%} of each other on {metric}. "
               "Version A stays and nothing changes in your playbook.")
    elif res["winner"] == "B":
        verdict = f'<mark class="mk">{ui.esc(agent._cap(b_txt))}</mark> won.'
        sub = f"{diff:.1%} more {metric} than {a_txt}. It joins your playbook."
    else:
        verdict = f'<mark class="mk">{ui.esc(agent._cap(a_txt))}</mark> held on.'
        sub = f"{agent._cap(b_txt)} got {abs(diff):.1%} less {metric}, so {a_txt} stays in your playbook."
    st.markdown(f'<div>{ui.tag("Simulated result", "sim")}</div><p class="verdict">{verdict}</p>'
                f'<div class="verdict-sub">{sub}</div>', unsafe_allow_html=True)
    with st.popover("How was this scored?", icon=":material/help:"):
        st.markdown(SCORING_HELP)

    left, right = st.columns([3, 2], gap="large")
    with left:
        ui.results_table(res)
        st.markdown('<div class="legend">' + " · ".join(
            f"<b>{ui.metric_label(m)}</b>: {agent.METRIC_HELP[m]}" for m in res["results"]["A"]) + "</div>",
                    unsafe_allow_html=True)
    with right:
        st.markdown('<div class="why-h" role="heading" aria-level="3">Saved to memory</div>'
                    f'<p class="lesson-quote">{ui.esc(res["learning"])}</p>'
                    '<div class="muted" style="margin-top:8px">Your next test starts from here.</div>',
                    unsafe_allow_html=True)

    s = res.get("strategy")
    if s:
        win_key = "A" if res.get("tie") else res["winner"]
        win = s["variant_a" if win_key == "A" else "variant_b"]
        st.markdown('<div class="step-title" role="heading" aria-level="2" style="margin-top:28px">'
                    'Ready to send</div><div class="step-sub" style="margin-bottom:10px">Version '
                    f'{win_key}, the one to keep. Copy it into your {"email tool" if ch == "email" else "Instagram post"}.'
                    '</div>', unsafe_allow_html=True)
        pv, txt = st.columns([1, 1], gap="large")
        with pv:
            ui.variant_preview(ch, win, win, res["plan"][win_key], None, "A", brand_name, profile)
        with txt:
            st.code(ui.plain_copy(ch, win), language=None, wrap_lines=True)
            st.caption("Use the copy button in the top-right corner of the box.")

    st.write("")
    keep = a_txt if res.get("tie") or res["winner"] == "A" else b_txt
    st.markdown(f'<div class="prose">Up next: version A keeps <b>{ui.esc(keep)}</b> and tests one new idea.</div>',
                unsafe_allow_html=True)
    n1, n2, _ = st.columns([1.2, 1.2, 3])
    if n1.button("Plan the next test", type="primary", icon=":material/arrow_forward:", width="stretch"):
        st.session_state.pop("last_result", None)
        st.rerun()
    if n2.button("See all results", icon=":material/insights:", width="stretch"):
        st.session_state.pop("last_result", None)
        go("results")


# ---------------- Brand profile ----------------
def brand_page():
    ui.page_header("Your brand", "Step 1 of 3 · Campaign Lab saves your brand to memory and uses it to "
                                 "write every version in your voice, with your logo and colors.")
    if profile and not st.session_state.get("reimport"):
        n1, n2, _ = st.columns([1.3, 1.6, 3])
        if n1.button("Run a test", type="primary", icon=":material/arrow_forward:", width="stretch"):
            go("create")
        if n2.button("Re-import from website", icon=":material/refresh:", width="stretch"):
            st.session_state.reimport = True
            st.rerun()
        with st.container(border=True):
            onboarding.render_brand_kit(profile)
        return

    with st.container(border=True):
        st.markdown("**Import from your website and Instagram**")
        st.caption("Demo: this reads a saved copy of the Kung Fu Kids website and Instagram.")
        c1, c2, c3 = st.columns([2, 2, 1], vertical_alignment="bottom")
        website_url = c1.text_input("Website URL", value="https://kungfukids.com")
        insta_handle = c2.text_input("Instagram handle", value="@wushucentral")
        do_import = c3.button("Import", type="primary", width="stretch")
    if do_import:
        scraped = onboarding.run_scrape_animation(website_url, insta_handle)
        onboarding.save_profile_to_memory(memory, user_id, profiles, scraped)
        st.session_state.pop("reimport", None)
        st.toast("Brand saved. Next: run your first test.", icon=":material/check:")
        st.rerun()


# ---------------- Memory ----------------
def memory_page():
    ui.page_header("Memory", f"Everything Campaign Lab remembers about {brand_name}: your brand, and one "
                             "lesson per test. You don't need to do anything here; the tests use it automatically.")
    q = st.text_input("Search memory", placeholder="e.g. what subject lines work for email?")
    if q:
        hits = memory.search(q)
        with st.container(border=True):
            for r in hits:
                st.markdown(f"- {r['memory']}  \n  <span class='muted'>{r['metadata'].get('kind', '')}</span>",
                            unsafe_allow_html=True)
            if not hits:
                st.caption("No matches. Try fewer words.")
    items = memory.all()
    if not items:
        st.info("Nothing remembered yet. Set up your brand to get started.", icon=":material/info:")
        if st.button("Set up your brand", type="primary"):
            go("brand")
        return
    kinds = sorted({m["metadata"].get("kind", "") for m in items})
    pick = st.pills("Filter", kinds, selection_mode="multi", default=kinds, label_visibility="collapsed")
    df = pd.DataFrame([{"Kind": m["metadata"].get("kind"), "Channel": m["metadata"].get("channel", ""),
                        "Memory": m["memory"], "Stored in": "Mem0" if m["synced_to_mem0"] else "This computer",
                        "Created": m["created_at"].replace("T", " ")}
                       for m in reversed(items) if m["metadata"].get("kind", "") in (pick or kinds)])
    st.dataframe(df, hide_index=True, width="stretch",
                 column_config={"Memory": st.column_config.TextColumn(width="large")})


sidebar()
PAGES = {"home": st.Page(home_page, title="Home", icon=":material/home:", default=True),
         "brand": st.Page(brand_page, title="1 · Your brand", icon=":material/palette:", url_path="brand"),
         "create": st.Page(create_page, title="2 · Run a test", icon=":material/science:", url_path="create"),
         "results": st.Page(results_page, title="3 · Results", icon=":material/insights:", url_path="results"),
         "memory": st.Page(memory_page, title="Memory", icon=":material/neurology:", url_path="memory")}
st.navigation({"": [PAGES["home"]],
               "Workflow": [PAGES["brand"], PAGES["create"], PAGES["results"]],
               "Reference": [PAGES["memory"]]}).run()
