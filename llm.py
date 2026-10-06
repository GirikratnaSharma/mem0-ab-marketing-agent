"""Claude copywriter: turns the plan + recalled Mem0 context into Variant A/B copy.

The agent's plan (which dimension to test, champion vs challenger config) stays
rule-based in agent.py so the simulated audience can score it. Claude writes the
actual copy for each variant, grounded in the brand memory and past learnings
from build_llm_context(). Without ANTHROPIC_API_KEY, or if a call fails, the
caller falls back to agent.render_copy().
"""
import json
import os

MODEL = "claude-opus-5-5"

SYSTEM = """You are the copywriter inside an A/B testing marketing agent for small businesses.
You receive what the agent remembers about the business and past A/B test results, plus
the exact configuration of each variant. Write copy that sounds like this brand and follows
each variant's configuration exactly: the two variants must differ ONLY in the dimension
under test, so the test stays fair. Keep proven winners from the learnings."""

SCHEMA = {
    "type": "object",
    "properties": {
        "A": {"type": "string", "description": "Variant A copy (markdown)"},
        "B": {"type": "string", "description": "Variant B copy (markdown)"},
        "rationale": {"type": "string",
                      "description": "One sentence: how the memories shaped this copy"},
    },
    "required": ["A", "B", "rationale"],
    "additionalProperties": False,
}

FORMATS = {
    "email": "For each variant write '**Subject:** <subject line>' then a blank line and a "
             "2-3 sentence email body. Use the literal placeholder {first_name} when "
             "personalization=first_name.",
    "instagram": "For each variant write '**[<format>]**' then the caption (2-3 sentences), "
                 "the call to action and the hashtags.",
}


def available() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def write_variants(channel: str, plan: dict, llm_context: str, brand_name: str) -> dict:
    """Return {"A": copy, "B": copy, "rationale": str}. Raises on API errors or refusals."""
    import anthropic

    client = anthropic.Anthropic()
    prompt = (
        f"{llm_context}\n\n"
        f"Brand name: {brand_name}\n"
        f"Dimension under test: {plan['tested_dimension']}\n"
        f"Variant A config: {json.dumps(plan['A'])}\n"
        f"Variant B config: {json.dumps(plan['B'])}\n\n"
        f"{FORMATS[channel]}"
    )
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=4000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined to write this copy")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)
