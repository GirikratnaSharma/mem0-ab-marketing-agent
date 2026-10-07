"""AI campaign strategist: turns recalled memory into a recommendation.

Input: the Mem0 recall (brand facts + A/B learnings) and the most similar past
campaign records. Output: what those records say, which ONE idea Variant B
should test next, and ready-to-ship copy for both variants.

Claude does the reasoning: directly via the Anthropic API when ANTHROPIC_API_KEY is
set, otherwise through OpenRouter when OPENROUTER_API_KEY is set. Without a working key
the offline strategist summarizes the records and picks an untested idea, so
the app still runs end to end.
"""
import os
import random
import re
from typing import Literal

import anthropic
import openai
import requests
from pydantic import BaseModel, Field

import agent

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-5-5")
# Free (zero-cost) default; set OPENROUTER_MODEL=anthropic/claude-opus-5.5 to use Claude with credit.
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-super-120b-a12b:free")
OPENROUTER_URL = "https://openrouter.ai/api/v1"


class VariantCopy(BaseModel):
    headline: str = Field(description="Email subject line, or the first line / hook of the Instagram caption")
    body: str = Field(description="Email body (2-3 short sentences, no hashtags, no button text), or the rest of the Instagram caption incl. hashtags")
    cta: str = Field(description="Button or call-to-action words the reader sees, e.g. 'Save my free class'. Never an option id like book_now.")
    visual: str = Field(description="One-line art direction for the image / video")


class Strategy(BaseModel):
    insights: list[str] = Field(description="2-3 plain-language takeaways from the past records, each citing the evidence")
    recommendation: str = Field(description="One short plain sentence naming the change, e.g. 'Try a question subject line instead of an urgent one.'")
    rationale: str = Field(description="2-3 sentences connecting the evidence to this test")
    test_dimension: str
    challenger_value: str
    hypothesis: str = Field(description="Falsifiable prediction, e.g. 'question hooks lift CTR vs urgency'")
    confidence: Literal["low", "medium", "high"]
    variant_a: VariantCopy
    variant_b: VariantCopy


SYSTEM = """You are the campaign strategist inside an A/B testing tool for small businesses.
Before each campaign you receive the business's brand profile, what the shared memory
recalls (past A/B learnings and brand facts), and the most similar past campaign records.

Your job:
1. Read the records and state what they tell us (insights). Cite the evidence (which
   option won, by how much, on which campaign). If there is no history, say so plainly
   and lean on general marketing knowledge for this kind of business.
2. Variant A is the current champion config and is fixed. Choose exactly ONE change for
   Variant B from the allowed test options. Prefer tests the evidence suggests could win
   big and that have not been tried; never re-test a known loser.
3. Write on-brand copy for both variants. The two must differ ONLY in the tested
   dimension, and each must visibly embody its config values:
   - subject_hook / hook: urgency = deadline; question = ends in "?"; number = leads with
     a number; curiosity = withholds the payoff; behind_the_scenes = how it's made or prepared;
     customer_quote = a quoted customer; showcase = shows the offer plainly.
   - personalization=first_name: include the literal token {first_name}.
   - emoji=yes: 1-2 emoji in the subject; emoji=no: none.
   - offer: discount = % off; free_trial = first visit / class free; bring_a_friend = friend
     comes free; none = no offer. Never contradict the brief (no discount on something free).
   - cta: book_now, link_in_bio, comment_to_win; hashtags: many = 6+, few = 1-2.
     Timing values don't appear in copy.
   - visual: one line of art direction a small business can shoot on a phone.
Write for a busy owner with no marketing background: plain sentences, no option ids,
no jargon like "CTR" or "variant". Most businesses here sell services (classes, food,
appointments), not shipped products. Be specific to this business; no generic filler."""


# ---------------- inputs ----------------
def similar_campaigns(campaigns: list, channel: str, brief: str, k: int = 5) -> list:
    """Past campaigns on this channel whose brief shares words with this one,
    most similar first, then most recent. Unrelated briefs are left out."""
    words = set(re.findall(r"[a-z]{4,}", brief.lower()))
    same = [c for c in campaigns if c["channel"] == channel]
    scored = [(len(words & set(re.findall(r"[a-z]{4,}", c["brief"].lower()))), i, c)
              for i, c in enumerate(same)]
    scored = [t for t in scored if t[0] > 0]
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return [c for _, _, c in scored[:k]]


def _campaign_line(c: dict) -> str:
    dim, ch = c["plan"]["tested_dimension"], c["channel"]
    a, b = c["plan"]["A"][dim], c["plan"]["B"][dim]
    if c.get("tie"):
        return (f"'{c['name']}' (brief: {c['brief']}): tested {dim}, {b} vs {a} too close to call "
                f"({c['lift']:.0%} apart)")
    win, lose = (b, a) if c["winner"] == "B" else (a, b)
    return (f"'{c['name']}' (brief: {c['brief']}): tested {dim}, {win} "
            f"({agent.option_label(ch, dim, win)}) beat {lose} by +{c['lift']:.0%} "
            f"{c['primary']} (winner {c['winner_score']:.2%})")


def build_prompt(context: dict, brief: str, channel: str, profile: dict,
                 champion: dict, options: list, past: list) -> str:
    lines = [f"Campaign brief: {brief}", f"Channel: {channel} "
             f"(primary metric: {agent.CHANNELS[channel]['primary']})", "", "Brand profile:"]
    for key in ("brand_name", "voice", "biz_type", "audience", "goals", "constraints"):
        if profile.get(key):
            lines.append(f"- {key}: {profile[key]}")
    if len(lines) == 4:
        lines.append("- (no onboarding yet)")
    lines += ["", "Recalled from memory: brand facts"]
    lines += [f"- {m['memory']}" for m in context["brand"]] or ["- (none)"]
    lines += ["", "Recalled from memory: A/B learnings (most relevant first)"]
    lines += [f"- {m['memory']}" for m in context["learnings"]] or ["- (none yet: first test on this channel)"]
    lines += ["", "Most similar past campaigns"]
    lines += [f"- {_campaign_line(c)}" for c in past] or ["- (none)"]
    lines += ["", "Variant A (champion, fixed): " + ", ".join(f"{k}={v}" for k, v in champion.items())]
    by_dim = {}
    for d, v in options:
        by_dim.setdefault(d, []).append(v)
    lines += ["", "Allowed tests for Variant B (dimension: value = meaning)"]
    lines += [f"- {d}: " + "; ".join(f"{v} = {agent.option_label(channel, d, v)}" for v in vs)
              for d, vs in by_dim.items()]
    return "\n".join(lines)


# ---------------- LLM ----------------
def provider() -> str | None:
    """Which route reaches the AI writer: the Anthropic API first, then OpenRouter."""
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.getenv("OPENROUTER_API_KEY"):
        return "openrouter"
    return None


def llm_status() -> tuple[bool, str]:
    """Is Claude usable? Checks the key without spending anything."""
    route = provider()
    if route is None:
        return False, "Offline strategist (set ANTHROPIC_API_KEY or OPENROUTER_API_KEY)"
    if route == "openrouter":
        try:
            r = requests.get(f"{OPENROUTER_URL}/key", timeout=10,
                             headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"})
            if r.status_code == 401:
                return False, "OpenRouter key invalid (offline strategist)"
            data = r.json().get("data", {})
            out_of_credit = data.get("limit_remaining") is not None and data["limit_remaining"] <= 0
            if out_of_credit and not OPENROUTER_MODEL.endswith(":free"):
                return False, "OpenRouter key has no credit left (offline strategist)"
        except (requests.RequestException, ValueError):
            pass  # network blip: let suggest() try and report
        return True, f"{writer_name('openrouter')} via OpenRouter"
    try:
        anthropic.Anthropic(timeout=10.0, max_retries=0).models.retrieve(MODEL)
    except anthropic.AuthenticationError:
        return False, "Claude key invalid (offline strategist)"
    except anthropic.NotFoundError:
        return False, f"Model {MODEL} not available (offline strategist)"
    except anthropic.APIError:
        pass  # network blip / rate limit: let suggest() try and report
    return True, f"Claude · {MODEL}"


def _ask_claude(prompt: str) -> Strategy:
    client = anthropic.Anthropic(timeout=180.0)
    kwargs = dict(model=MODEL, max_tokens=16000, output_config={"effort": "medium"},
                  system=SYSTEM, messages=[{"role": "user", "content": prompt}],
                  output_format=Strategy)
    try:
        response = client.beta.messages.parse(
            betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs)
    except anthropic.BadRequestError as e:
        if "fallback" not in str(e.message).lower():
            raise
        response = client.messages.parse(**kwargs)
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined this request.")
    if response.parsed_output is None:
        raise RuntimeError(f"No strategy returned (stop_reason={response.stop_reason}).")
    return response.parsed_output


def _ask_openrouter(prompt: str) -> Strategy:
    """Claude through OpenRouter's OpenAI-compatible API, with a strict JSON schema."""
    client = openai.OpenAI(api_key=os.environ["OPENROUTER_API_KEY"], base_url=OPENROUTER_URL,
                           timeout=180.0, default_headers={"X-Title": "Campaign Lab"})
    response = client.chat.completions.create(
        model=OPENROUTER_MODEL, max_tokens=16000,
        messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
        response_format={"type": "json_schema", "json_schema": {
            "name": "Strategy", "strict": True, "schema": Strategy.model_json_schema()}})
    choice = response.choices[0]
    if not choice.message.content:
        raise RuntimeError(f"No strategy returned (finish_reason={choice.finish_reason}).")
    return Strategy.model_validate_json(choice.message.content)


def writer_name(source: str) -> str:
    """Human name of the model that wrote a plan, for labels."""
    if source == "claude":
        return "Claude"
    if source == "openrouter":
        name = OPENROUTER_MODEL.split("/")[-1].removesuffix(":free")
        pretty = {"nemotron-3-super-120b-a12b": "Nemotron 3 Super"}.get(name, name)
        return f"{pretty} (free)" if OPENROUTER_MODEL.endswith(":free") else pretty
    return "the built-in strategist"


def _ask(prompt: str) -> Strategy:
    return _ask_openrouter(prompt) if provider() == "openrouter" else _ask_claude(prompt)


def _error_text(e: Exception) -> str:
    if isinstance(e, anthropic.AuthenticationError):
        return "Anthropic API key was rejected (401). Check ANTHROPIC_API_KEY in .env."
    if isinstance(e, anthropic.RateLimitError):
        return "Anthropic rate limit hit. Try again in a minute."
    if isinstance(e, anthropic.APIConnectionError):
        return "Couldn't reach the Anthropic API (network)."
    if isinstance(e, anthropic.APIStatusError):
        return f"Anthropic API error {e.status_code}: {e.message}"
    if isinstance(e, openai.AuthenticationError):
        return "OpenRouter key was rejected (401). Check OPENROUTER_API_KEY in .env."
    if isinstance(e, (openai.PermissionDeniedError, openai.APIStatusError)) and \
            getattr(e, "status_code", None) in (402, 403):
        return "OpenRouter key is out of credit or over its spending limit. Raise it at openrouter.ai/settings/keys."
    if isinstance(e, openai.RateLimitError):
        return "OpenRouter rate limit hit. Try again in a minute."
    if isinstance(e, openai.APIConnectionError):
        return "Couldn't reach OpenRouter (network)."
    if isinstance(e, openai.APIStatusError):
        return f"OpenRouter error {e.status_code}: {e.message}"
    return str(e)


# ---------------- offline fallback ----------------
def _lesson_line(channel, md) -> str:
    win = agent.option_label(channel, md["dimension"], md["winner"])
    lose = agent.option_label(channel, md["dimension"], md["loser"])
    if md.get("tie"):
        return f"{agent._cap(lose)} and {win} were too close to call."
    return f"{agent._cap(win)} beat {lose} by {md.get('lift', 0):.0%}."


def relevant_lessons(memory, channel: str, dim: str, k: int = 3) -> list:
    """Past lessons for this channel: the setting being tested first, then the most recent."""
    lessons = [m["metadata"] for m in memory.all(kind="learning") if m["metadata"].get("channel") == channel]
    ranked = sorted(enumerate(lessons), key=lambda t: (t[1].get("dimension") == dim, t[0]), reverse=True)
    return [md for _, md in ranked[:k]]


def _offline(memory, brief, channel, profile, champion, options, round_no, avoid=(), force=None,
             use_memory=True) -> dict:
    lessons = [m["metadata"] for m in memory.all(kind="learning")
               if m["metadata"].get("channel") == channel] if use_memory else []
    tested_dims = {md["dimension"] for md in lessons}
    if force and tuple(force) in options:
        dim, val = force
    else:
        pool = [o for o in options if o not in avoid] or options
        fresh = [o for o in pool if o[0] not in tested_dims] or pool
        dim, val = random.Random(f"{channel}-{round_no}-{brief}-{len(avoid)}").choice(fresh)
    what = agent.DIMENSION_LABELS[dim]
    same_dim = [md for md in lessons if md["dimension"] == dim]
    insights = [_lesson_line(channel, md) for md in relevant_lessons(memory, channel, dim)] if use_memory else []
    if not insights:
        insights = [f"This is your first {'email' if channel == 'email' else 'Instagram'} test, so there's "
                    "no history yet. It sets the baseline the next tests build on."]
    if not lessons:
        rationale = ("With no past results, version A uses common best practice and "
                     f"version B changes only the {what}, so the result is easy to read.")
    elif not same_dim:
        rationale = (f"You haven't tested the {what} yet, so this test teaches the most. "
                     "Everything that already won stays the same in both versions.")
    else:
        rationale = (f"Your current {what} won before. {agent._cap(agent.option_label(channel, dim, val))} "
                     "is the next option worth putting against it.")
    if force:
        rationale = f"You chose this test. Only the {what} changes, so the result is easy to read."
    brand = profile.get("brand_name", "your business")
    return {
        "insights": insights,
        "recommendation": agent.describe_change(channel, dim, champion[dim], val),
        "rationale": rationale,
        "test_dimension": dim, "challenger_value": val,
        "hypothesis": (f"{agent._cap(agent.option_label(channel, dim, val))} gets more "
                       f"{agent.METRIC_LABELS[agent.CHANNELS[channel]['primary']].lower()} than "
                       f"{agent.option_label(channel, dim, champion[dim])}."),
        "confidence": "medium" if same_dim else "low",
        "variant_a": agent.template_copy(channel, champion, brief, brand),
        "variant_b": agent.template_copy(channel, {**champion, dim: val}, brief, brand),
    }


def _readable_cta(channel, cta: str) -> str:
    """Turn an option id the model echoed (book_now) into words a reader would see."""
    ids = {"book_now": "Book now", "link_in_bio": "Link in bio", "comment_to_win": "Comment to win"}
    raw = (cta or "").strip()
    if raw in ids:
        return ids[raw]
    return raw.replace("_", " ").capitalize() if raw and " " not in raw and "_" in raw else raw


# ---------------- entry point ----------------
def suggest(memory, channel: str, brief: str, profile: dict, campaigns: list,
            use_memory: bool = True, round_no: int = 1, avoid=(), force=None) -> dict:
    """Recall -> reason over past records -> plan + copy.
    `avoid` lists tests already suggested; `force` is a (dimension, value) the owner picked.
    Returns {plan, strategy, source, error, prompt, context, past, options, locks, ...}."""
    context = agent.recall(memory, channel, brief) if use_memory else \
        {"brand": [], "learnings": [], "playbook": None}
    locks = agent.brief_locks(channel, brief)
    champion, options = agent.test_options(memory, channel, use_memory, locks)
    past = similar_campaigns(campaigns, channel, brief) if use_memory else []
    avoid = [tuple(a) for a in avoid]
    force = tuple(force) if force else None
    prompt = build_prompt(context, brief, channel, profile, champion, options, past)
    if locks:
        prompt += ("\n\nThe brief already decides: " + ", ".join(f"{d}={v}" for d, v in locks.items())
                   + ". Keep it in both versions; don't test it.")
    if force:
        prompt += f"\n\nThe owner chose the test: {force[0]}={force[1]}. Use exactly this test."
    elif avoid:
        prompt += ("\n\nThe owner asked for a different idea. Don't suggest these again: "
                   + "; ".join(f"{d}={v}" for d, v in avoid))

    def offline():
        return _offline(memory, brief, channel, profile, champion, options, round_no, avoid, force, use_memory)

    strategy, source, error = None, "offline", None
    if provider():
        try:
            strategy = _ask(prompt).model_dump()
            source = "openrouter" if provider() == "openrouter" else "claude"
        except Exception as e:  # never break the campaign flow on an LLM failure
            error = _error_text(e)
    if strategy is None:
        strategy = offline()
    elif (strategy["test_dimension"], strategy["challenger_value"]) not in options or \
            (force and (strategy["test_dimension"], strategy["challenger_value"]) != force):
        # The model proposed a test outside the allowed set: keep its insights, swap the test.
        fallback = offline()
        for key in ("test_dimension", "challenger_value", "variant_a", "variant_b", "recommendation",
                    "rationale", "hypothesis"):
            strategy[key] = fallback[key]
        error = "The AI suggested a test we can't run, so the built-in strategist wrote this one."
        source = "offline"  # the copy on screen is the template's, so label it that way

    # House style for the headline and an evidence-based confidence, whoever wrote the plan:
    # models leak option ids into prose and overstate certainty.
    dim, val = strategy["test_dimension"], strategy["challenger_value"]
    strategy["recommendation"] = agent.describe_change(channel, dim, champion[dim], val)
    has_evidence = use_memory and any(m["metadata"].get("channel") == channel and m["metadata"].get("dimension") == dim
                                      for m in memory.all(kind="learning"))
    strategy["confidence"] = "medium" if has_evidence else "low"
    for key in ("variant_a", "variant_b"):
        strategy[key]["cta"] = _readable_cta(channel, strategy[key]["cta"])
    p = agent.make_plan(champion, dim, val, strategy["recommendation"])
    n_tests = len([m for m in memory.all(kind="learning") if m["metadata"].get("channel") == channel]) \
        if use_memory else 0
    return {"plan": p, "strategy": strategy, "source": source, "error": error, "n_tests": n_tests,
            "prompt": prompt, "context": context, "past": past, "options": options, "locks": locks,
            "suggested": [*avoid, (strategy["test_dimension"], strategy["challenger_value"])]}
