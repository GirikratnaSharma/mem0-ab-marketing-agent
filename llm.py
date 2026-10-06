"""LLM copywriter: turns the plan + recalled Mem0 context into Variant A/B copy.

Provider, first one configured wins:
- Ollama (free, local) when OLLAMA_MODEL is set, e.g. OLLAMA_MODEL=qwen3:8b
- Kimi (Moonshot) when KIMI_API_KEY is set
- Claude when ANTHROPIC_API_KEY is set
Ollama and Kimi both speak the OpenAI-compatible API, so they share one code path.

The agent's plan (which dimension to test, champion vs challenger config) stays
rule-based in agent.py so the simulated audience can score it. The LLM writes the
actual copy for each variant, grounded in the brand memory and past learnings
from build_llm_context(). Without either key, or if a call fails, the caller
falls back to agent.render_copy().
"""
import json
import os

MODEL = "claude-opus-5-5"
KIMI_MODEL = "kimi-k2.6"
KIMI_BASE_URL = "https://api.moonshot.ai/v1"
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")

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


def provider() -> str | None:
    if os.getenv("OLLAMA_MODEL"):
        return "Ollama"
    if os.getenv("KIMI_API_KEY"):
        return "Kimi"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "Claude"
    return None


def available() -> bool:
    return provider() is not None


def write_variants(channel: str, plan: dict, llm_context: str, brand_name: str) -> dict:
    """Return {"A": copy, "B": copy, "rationale": str}. Raises on API errors or refusals."""
    prompt = (
        f"{llm_context}\n\n"
        f"Brand name: {brand_name}\n"
        f"Dimension under test: {plan['tested_dimension']}\n"
        f"Variant A config: {json.dumps(plan['A'])}\n"
        f"Variant B config: {json.dumps(plan['B'])}\n\n"
        f"{FORMATS[channel]}"
    )
    if provider() == "Ollama":
        out = _openai_compatible(prompt, OLLAMA_BASE_URL, "ollama", os.environ["OLLAMA_MODEL"])
    elif provider() == "Kimi":
        out = _openai_compatible(prompt, KIMI_BASE_URL, os.environ["KIMI_API_KEY"], KIMI_MODEL)
    else:
        out = _claude(prompt)
    if not all(isinstance(out.get(k), str) for k in ("A", "B", "rationale")):
        raise ValueError(f"unexpected copywriter output: {out}")
    return out


def _openai_compatible(prompt: str, base_url: str, api_key: str, model: str) -> dict:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM + "\n\nReply with only a JSON object matching "
                                          "this schema: " + json.dumps(SCHEMA)},
            {"role": "user", "content": prompt},
        ],
    )
    return json.loads(response.choices[0].message.content)


def _claude(prompt: str) -> dict:
    import anthropic

    client = anthropic.Anthropic()
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
