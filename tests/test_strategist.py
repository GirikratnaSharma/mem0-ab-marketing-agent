"""Tests for the AI strategist: prompt built from past records, Claude path (mocked), offline fallback."""
import pytest

import agent
import memory_store
import strategist
from memory_store import MemoryStore


@pytest.fixture(autouse=True)
def isolated_mirror(tmp_path, monkeypatch):
    monkeypatch.setattr(memory_store, "MIRROR_PATH", tmp_path / "memories.json")


@pytest.fixture(autouse=True)
def no_real_llm_keys(monkeypatch):
    """Other tests load .env; never let these tests reach a real LLM."""
    for k in ("ANTHROPIC_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(k, raising=False)


@pytest.fixture
def mem():
    m = MemoryStore("test_strategist")
    m.client = None
    return m


PROFILE = {"brand_name": "Kung Fu Kids", "voice": "Playful and high-energy.", "audience": "children and families"}


def _seed(mem, channel="email", rounds=2):
    camps = []
    for r in range(1, rounds + 1):
        p = agent.plan(mem, channel, True, r)
        res = {k: agent.simulate(channel, p[k], f"s-{r}-{k}") for k in "AB"}
        out = agent.learn(mem, channel, p, res, f"Email #{r}: summer camp")
        primary = agent.CHANNELS[channel]["primary"]
        camps.append({"name": f"Email #{r}: summer camp", "channel": channel, "brief": "summer camp promo",
                      "plan": p, "winner": out["winner"], "lift": out["lift"], "primary": primary,
                      "winner_score": res[out["winner"]][primary]})
    return camps


def _copy(h):
    return strategist.VariantCopy(headline=h, body="b", cta="c", visual="v")


def test_similar_campaigns_ranks_by_brief_overlap():
    camps = [{"channel": "email", "brief": "winter holiday sale"},
             {"channel": "email", "brief": "summer camp enrollment"},
             {"channel": "instagram", "brief": "summer camp enrollment"}]
    out = strategist.similar_campaigns(camps, "email", "Summer camp early bird")
    assert [c["brief"] for c in out] == ["summer camp enrollment"]  # unrelated briefs aren't "similar"


def test_prompt_contains_past_records_and_allowed_tests(mem):
    camps = _seed(mem)
    context = agent.recall(mem, "email", "summer camp")
    champion, options = agent.test_options(mem, "email")
    prompt = strategist.build_prompt(context, "summer camp", "email", PROFILE, champion, options, camps)
    assert "Kung Fu Kids" in prompt
    assert all(c["name"] in prompt for c in camps)
    assert "Allowed tests for Variant B" in prompt
    tested = {(m["metadata"]["dimension"], m["metadata"]["loser"]) for m in mem.all(kind="learning")}
    assert not tested & set(options)  # known losers are never offered again


def test_offline_fallback_without_key(mem, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    camps = _seed(mem)
    out = strategist.suggest(mem, "email", "summer camp", PROFILE, camps, True, 3)
    assert out["source"] == "offline" and out["error"] is None
    p, s = out["plan"], out["strategy"]
    dim = p["tested_dimension"]
    assert p["A"][dim] != p["B"][dim]
    assert {k for k in p["A"] if p["A"][k] != p["B"][k]} == {dim}
    assert any("beat" in i for i in s["insights"])  # insights come from the records
    assert s["variant_a"]["headline"] and s["variant_b"]["headline"]


def test_claude_strategy_is_used_when_valid(mem, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    _, options = agent.test_options(mem, "email")
    dim, val = options[0]
    fake = strategist.Strategy(insights=["x"], recommendation="Test it", rationale="because",
                               test_dimension=dim, challenger_value=val, hypothesis="h",
                               confidence="medium", variant_a=_copy("A!"), variant_b=_copy("B?"))
    seen = {}
    monkeypatch.setattr(strategist, "_ask_claude", lambda prompt: seen.setdefault("p", prompt) and fake)
    out = strategist.suggest(mem, "email", "summer camp", PROFILE, [], True, 1)
    assert out["source"] == "claude" and out["error"] is None
    assert out["plan"]["B"][dim] == val and out["strategy"]["variant_b"]["headline"] == "B?"
    assert "summer camp" in seen["p"]


def test_invalid_claude_test_is_replaced(mem, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    fake = strategist.Strategy(insights=["keep me"], recommendation="r", rationale="r",
                               test_dimension="font", challenger_value="comic_sans", hypothesis="h",
                               confidence="high", variant_a=_copy("a"), variant_b=_copy("b"))
    monkeypatch.setattr(strategist, "_ask_claude", lambda prompt: fake)
    out = strategist.suggest(mem, "email", "summer camp", PROFILE, [], True, 1)
    _, options = agent.test_options(mem, "email")
    assert (out["plan"]["tested_dimension"], out["plan"]["B"][out["plan"]["tested_dimension"]]) in options
    assert out["strategy"]["insights"] == ["keep me"] and out["error"]
    assert out["source"] == "offline"  # the swapped-in copy is the template's


def test_api_failure_falls_back_offline(mem, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")

    def boom(prompt):
        raise RuntimeError("network down")
    monkeypatch.setattr(strategist, "_ask_claude", boom)
    out = strategist.suggest(mem, "instagram", "summer camp", PROFILE, [], True, 1)
    assert out["source"] == "offline" and "network down" in out["error"]
    assert out["plan"]["tested_dimension"] in agent.CHANNELS["instagram"]["dimensions"]


def test_suggest_a_different_test_avoids_previous(mem, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    first = strategist.suggest(mem, "email", "summer camp", PROFILE, [], True, 1)
    picked = (first["plan"]["tested_dimension"], first["plan"]["B"][first["plan"]["tested_dimension"]])
    again = strategist.suggest(mem, "email", "summer camp", PROFILE, [], True, 1, first["suggested"])
    dim = again["plan"]["tested_dimension"]
    assert (dim, again["plan"]["B"][dim]) != picked
    assert len(again["suggested"]) == 2


def test_brand_color_is_darkened_until_white_text_passes():
    import ui
    c = ui.readable_on_white_text("#FF0000")
    assert 1.05 / (ui._lum(c) + 0.05) >= 4.5
    assert ui.readable_on_white_text("#113472") == "#113472"  # already readable
    assert ui.readable_on_white_text("not-a-color") == "#1C1A17"


def test_openrouter_route_is_used_without_anthropic_key(mem, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    assert strategist.provider() == "openrouter"
    _, options = agent.test_options(mem, "email")
    dim, val = options[0]
    fake = strategist.Strategy(insights=["x"], recommendation="r", rationale="r", test_dimension=dim,
                               challenger_value=val, hypothesis="h", confidence="low",
                               variant_a=_copy("a"), variant_b=_copy("b"))
    monkeypatch.setattr(strategist, "_ask_openrouter", lambda prompt: fake)
    out = strategist.suggest(mem, "email", "summer camp", PROFILE, [], True, 1)
    assert out["source"] == "openrouter" and out["plan"]["B"][dim] == val


def test_out_of_credit_message_is_actionable():
    import httpx2 as httpx  # the openai SDK is built on httpx2
    req = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    err = __import__("openai").PermissionDeniedError(
        "Key limit exceeded", response=httpx.Response(403, request=req), body=None)
    assert "spending limit" in strategist._error_text(err)


def test_offer_named_in_brief_is_locked_not_tested(mem):
    out = strategist.suggest(mem, "email", "Fall session: free trial class for new kids", PROFILE, [], True, 1)
    assert out["locks"] == {"offer": "free_trial"}
    assert out["plan"]["A"]["offer"] == out["plan"]["B"]["offer"] == "free_trial"
    assert all(d != "offer" for d, _ in out["options"])
    assert "Members save 20%" not in out["strategy"]["variant_a"]["body"]


def test_owner_can_choose_the_test(mem):
    first = strategist.suggest(mem, "instagram", "Belt test Saturday", PROFILE, [], True, 1)
    choice = next(o for o in first["options"] if o != first["suggested"][-1])
    out = strategist.suggest(mem, "instagram", "Belt test Saturday", PROFILE, [], True, 1, force=choice)
    assert (out["plan"]["tested_dimension"], out["plan"]["B"][out["plan"]["tested_dimension"]]) == tuple(choice)
    assert "You chose this test" in out["strategy"]["rationale"]


def test_evidence_puts_the_tested_setting_first(mem):
    camps = _seed(mem, rounds=3)
    dims = [c["plan"]["tested_dimension"] for c in camps]
    ranked = strategist.relevant_lessons(mem, "email", dims[0])
    assert ranked[0]["dimension"] == dims[0]          # same setting first
    assert [md["dimension"] for md in ranked[1:]] == dims[1:][::-1]  # then most recent


def test_template_never_pastes_a_long_brief():
    long = "We are opening a brand new location in Palo Alto next month and spots are limited to 30"
    assert agent.short_topic(long) == "What's new"
    assert agent.short_topic("Belt test Saturday, parents welcome") == "Belt test Saturday"
    copy = agent.template_copy("email", agent.NAIVE_DEFAULTS["email"], long, "Kung Fu Kids")
    assert "Palo Alto" not in copy["body"] + copy["headline"]
