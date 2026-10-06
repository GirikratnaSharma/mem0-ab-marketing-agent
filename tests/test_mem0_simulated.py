"""Tests for the memory loop using the simulated onboarding data (Kung Fu Kids fixtures)
and the simulated audience in agent.py.

Offline tests always run (MemoryStore with the Mem0 client off, local JSON mirror only).
Live tests talk to the real Mem0 Platform and only run when MEM0_API_KEY is set:
    pytest                 # everything that can run
    pytest -m "not live"   # offline only
"""
import ast
import json
import os
import time
import uuid
from pathlib import Path

import pytest
from dotenv import load_dotenv

import agent
import memory_store
from memory_store import MemoryStore

ROOT = Path(__file__).resolve().parent.parent
ONBOARD_DIR = ROOT / "data" / "business-onboarding"
load_dotenv(ROOT / ".env")


def _load_app_function(name):
    """Pull one function out of app.py without running the Streamlit app."""
    tree = ast.parse((ROOT / "app.py").read_text())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    namespace = {}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "app.py", "exec"), namespace)
    return namespace[name]


build_profile_from_scrape = _load_app_function("build_profile_from_scrape")


def onboarding_memories(profile):
    """The two memories app.py's onboarding writes when a profile is saved."""
    return [
        (f"Brand: {profile['brand_name']}. Voice: {profile['voice']}. Rules: {profile['constraints']}",
         {"kind": "brand", "section": "brand_info"}),
        (f"Business: {profile['biz_type']}. Audience: {profile['audience']}. Goals: {profile['goals']}",
         {"kind": "brand", "section": "business_info"}),
    ]


@pytest.fixture
def website():
    return json.loads((ONBOARD_DIR / "website.json").read_text())["data"]


@pytest.fixture
def insta():
    return json.loads((ONBOARD_DIR / "instagram.json").read_text())[0]


@pytest.fixture
def profile(website, insta):
    return build_profile_from_scrape("https://kungfu.kids", "@wushucentral", website, insta)


@pytest.fixture(autouse=True)
def isolated_mirror(tmp_path, monkeypatch):
    """Never touch the app's real data/memories.json."""
    monkeypatch.setattr(memory_store, "MIRROR_PATH", tmp_path / "memories.json")


@pytest.fixture
def local_memory():
    m = MemoryStore("test_offline")
    m.client = None
    return m


# ---------------- simulated onboarding data ----------------
def test_fixtures_have_fields_onboarding_reads(website, insta):
    branding = website["branding"]
    assert branding["brandName"]
    assert {"tone", "energy", "targetAudience"} <= set(branding["personality"])
    assert branding["colors"] and branding["typography"]["fontFamilies"]
    assert website["summary"] and website["screenshot"]
    for key in ("username", "fullName", "biography", "followersCount", "businessCategoryName"):
        assert insta.get(key) not in (None, ""), key


def test_profile_built_from_simulated_scrape(profile):
    assert profile["brand_name"] == "Kung Fu Kids®"
    assert profile["voice"] == "Playful and high-energy."
    assert profile["audience"] == "children and families"
    assert profile["biz_type"] == "Martial Arts School"
    assert profile["followers"] == 1643
    assert profile["logo"].startswith("https://")


def test_onboarding_memories_stored_and_recalled_locally(profile, local_memory):
    for text, md in onboarding_memories(profile):
        local_memory.add(text, md, infer=True)
    brand = local_memory.all(kind="brand")
    assert len(brand) == 2
    assert "Kung Fu Kids" in brand[0]["memory"]
    hits = local_memory.search("brand voice business audience", filters={"kind": "brand"})
    assert {h["metadata"]["section"] for h in hits} == {"brand_info", "business_info"}


# ---------------- simulated audience + learning loop ----------------
@pytest.mark.parametrize("channel", ["email", "instagram"])
def test_simulated_audience_is_deterministic_and_complete(channel):
    cfg = agent.NAIVE_DEFAULTS[channel]
    a = agent.simulate(channel, cfg, "seed-1")
    assert a == agent.simulate(channel, cfg, "seed-1")
    assert set(a) == set(agent.CHANNELS[channel]["metrics"])
    assert all(v > 0 for v in a.values())


@pytest.mark.parametrize("channel", ["email", "instagram"])
def test_learn_writes_learning_and_playbook(channel, local_memory):
    p = agent.plan(local_memory, channel, True, 1)
    results = {k: agent.simulate(channel, p[k], f"t-{k}") for k in "AB"}
    out = agent.learn(local_memory, channel, p, results, "test campaign")

    primary = agent.CHANNELS[channel]["primary"]
    expected = "B" if results["B"][primary] > results["A"][primary] else "A"
    assert out["winner"] == expected
    (learning,) = local_memory.all(kind="learning")
    md = learning["metadata"]
    assert md["channel"] == channel and md["dimension"] == p["tested_dimension"]
    assert md["winner"] == p[expected][p["tested_dimension"]]
    assert local_memory.all(kind="playbook")[-1]["metadata"]["config"] == p[expected]


@pytest.mark.parametrize("channel", ["email", "instagram"])
def test_memory_beats_no_memory_on_simulated_audience(channel, tmp_path, monkeypatch):
    """The core demo claim: with memory the agent climbs toward the hidden best config."""
    def final_score(use_memory):
        monkeypatch.setattr(memory_store, "MIRROR_PATH", tmp_path / f"{use_memory}.json")
        m = MemoryStore(f"bench_{use_memory}")
        m.client = None
        primary = agent.CHANNELS[channel]["primary"]
        for r in range(1, 9):
            p = agent.plan(m, channel, use_memory, r)
            res = {k: agent.simulate(channel, p[k], f"b-{channel}-{r}-{k}-{use_memory}") for k in "AB"}
            agent.learn(m, channel, p, res, f"round {r}")
        champion, _ = agent._champion_from_memory(m, channel)
        return sum(agent.HIDDEN_PREFS[channel][d][v] for d, v in champion.items()) if use_memory \
            else sum(agent.HIDDEN_PREFS[channel][d][v] for d, v in agent.NAIVE_DEFAULTS[channel].items())

    assert final_score(True) > final_score(False)


# ---------------- live Mem0 ----------------
live = pytest.mark.skipif(not os.getenv("MEM0_API_KEY"), reason="MEM0_API_KEY not set")


def _wait_for(mem, sections, contains=(), timeout=120):
    """Mem0 adds are processed asynchronously: one add can become several memories, and a
    memory can be written first and then updated as facts merge. Poll until a memory from
    every expected metadata section/kind exists and the text holds every `contains` phrase."""
    found = []
    for _ in range(timeout // 3):
        found = mem.client.get_all(filters={"AND": [{"user_id": mem.user_id}]}, page_size=50)["results"]
        seen = {m["metadata"].get("section") or m["metadata"].get("kind") for m in found}
        text = " ".join(m["memory"] for m in found).lower()
        if set(sections) <= seen and all(c in text for c in contains):
            return found
        time.sleep(3)
    return found


@pytest.fixture
def live_memory():
    m = MemoryStore(f"test_kungfu_kids_{uuid.uuid4().hex[:8]}")
    assert m.client is not None, m.last_error
    yield m
    m.reset()


@live
@pytest.mark.live
def test_live_onboarding_brand_lands_in_mem0(profile, live_memory):
    for text, md in onboarding_memories(profile):
        live_memory.add(text, md, infer=True)
    assert live_memory.last_error is None

    stored = _wait_for(live_memory, ["brand_info", "business_info"],
                       contains=["kung fu kids", "children"])
    assert {m["metadata"]["section"] for m in stored} == {"brand_info", "business_info"}, stored
    assert all(m["metadata"]["kind"] == "brand" for m in stored)
    joined = " ".join(m["memory"] for m in stored).lower()
    assert "kung fu kids" in joined and "children" in joined

    hits = live_memory.search("brand voice business audience", filters={"kind": "brand"})
    assert hits and all(h["source"] == "mem0" for h in hits)


@live
@pytest.mark.live
def test_live_learning_recalled_for_next_campaign(profile, live_memory):
    for text, md in onboarding_memories(profile):
        live_memory.add(text, md, infer=True)
    p = agent.plan(live_memory, "email", True, 1)
    results = {k: agent.simulate("email", p[k], f"live-{k}") for k in "AB"}
    out = agent.learn(live_memory, "email", p, results, "Kids summer camp promo")
    assert live_memory.last_error is None
    _wait_for(live_memory, ["brand_info", "business_info", "learning", "playbook"])

    context = agent.recall(live_memory, "email", "Kids summer camp promo")
    assert any(m["source"] == "mem0" and m["memory"] == out["learning"] for m in context["learnings"])
    assert context["brand"] and all(m["metadata"]["kind"] == "brand" for m in context["brand"])


@live
@pytest.mark.live
def test_live_reset_clears_mem0(profile, live_memory):
    live_memory.add(*onboarding_memories(profile)[0], infer=False)
    assert _wait_for(live_memory, ["brand_info"])
    live_memory.reset()
    assert live_memory.last_error is None
    assert live_memory.client.get_all(filters={"AND": [{"user_id": live_memory.user_id}]},
                                      page_size=50)["results"] == []
