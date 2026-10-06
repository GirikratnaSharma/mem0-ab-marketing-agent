"""A/B testing marketing agent (placeholder logic).

Loop per campaign round:
  1. recall()      -> pull past learnings for this channel from memory
  2. plan()        -> Variant A = current champion (built from learnings),
                      Variant B = champion with ONE dimension changed (challenger)
  3. simulate()    -> simulated audience returns channel metrics
  4. learn()       -> compare A vs B, write the learning + updated playbook back to memory

PLACEHOLDER: plan() and render_copy() are rule-based today. In the future the
recalled Mem0 context is re-fed into an LLM prompt (see build_llm_context) so the
model writes the variants and explains its choices.
"""
import hashlib
import random

# ---------------- channel config ----------------
CHANNELS = {
    "email": {
        "dimensions": {
            "subject_hook": ["urgency", "question", "number", "curiosity"],
            "offer": ["discount", "free_shipping", "exclusive_access", "none"],
            "personalization": ["first_name", "none"],
            "emoji": ["yes", "no"],
            "send_time": ["morning", "evening"],
        },
        "metrics": ["open_rate", "ctr", "conversion_rate"],
        "primary": "ctr",
        "base": {"open_rate": 0.22, "ctr": 0.025, "conversion_rate": 0.008},
    },
    "instagram": {
        "dimensions": {
            "format": ["single_image", "carousel", "reel"],
            "hook": ["product_shot", "question", "behind_the_scenes", "ugc_testimonial"],
            "cta": ["shop_now", "link_in_bio", "comment_to_win"],
            "hashtags": ["many", "few"],
            "post_time": ["morning", "evening"],
        },
        "metrics": ["reach", "engagement_rate", "saves", "ctr"],
        "primary": "engagement_rate",
        "base": {"reach": 4000, "engagement_rate": 0.03, "saves": 40, "ctr": 0.008},
    },
}

# Hidden audience preferences: the "ground truth" the agent has to discover.
# Obvious defaults (discount, emoji, product shots, hashtag spam) are deliberately mediocre.
HIDDEN_PREFS = {
    "email": {
        "subject_hook": {"urgency": -0.05, "question": 0.25, "number": 0.10, "curiosity": 0.15},
        "offer": {"discount": 0.0, "free_shipping": 0.12, "exclusive_access": 0.30, "none": -0.15},
        "personalization": {"first_name": 0.20, "none": 0.0},
        "emoji": {"yes": -0.05, "no": 0.05},
        "send_time": {"morning": 0.12, "evening": 0.0},
    },
    "instagram": {
        "format": {"single_image": 0.0, "carousel": 0.20, "reel": 0.35},
        "hook": {"product_shot": 0.0, "question": 0.10, "behind_the_scenes": 0.30, "ugc_testimonial": 0.22},
        "cta": {"shop_now": 0.0, "link_in_bio": 0.05, "comment_to_win": 0.25},
        "hashtags": {"many": -0.08, "few": 0.08},
        "post_time": {"morning": 0.0, "evening": 0.15},
    },
}

NAIVE_DEFAULTS = {
    "email": {"subject_hook": "urgency", "offer": "discount", "personalization": "none",
              "emoji": "yes", "send_time": "evening"},
    "instagram": {"format": "single_image", "hook": "product_shot", "cta": "shop_now",
                  "hashtags": "many", "post_time": "morning"},
}


# ---------------- 1. recall ----------------
def recall(memory, channel: str, brief: str) -> dict:
    """Pull brand info + past learnings for this channel."""
    brand = memory.search(f"brand voice business audience {brief}", filters={"kind": "brand"}, top_k=5)
    learnings = memory.search(f"{channel} A/B test learnings what worked {brief}",
                              filters={"kind": "learning", "channel": channel}, top_k=10)
    playbook = [m for m in memory.all(kind="playbook") if m["metadata"].get("channel") == channel]
    return {"brand": brand, "learnings": learnings, "playbook": playbook[-1] if playbook else None}


def build_llm_context(context: dict, brief: str, channel: str) -> str:
    """FUTURE: this string is re-fed into the LLM system prompt so the model
    writes variants grounded in Mem0 memories. Shown in the UI today."""
    lines = [f"Campaign brief: {brief}", f"Channel: {channel}", "", "Brand memory:"]
    lines += [f"- {m['memory']}" for m in context["brand"]] or ["- (none)"]
    lines += ["", "Past A/B learnings (most relevant first):"]
    lines += [f"- {m['memory']}" for m in context["learnings"]] or ["- (none yet: first test)"]
    if context["playbook"]:
        lines += ["", f"Current playbook: {context['playbook']['memory']}"]
    lines += ["", "Task: keep proven winners, test exactly ONE new idea in Variant B."]
    return "\n".join(lines)


# ---------------- 2. plan ----------------
def _champion_from_memory(memory, channel: str) -> tuple[dict, set]:
    """PLACEHOLDER for LLM reasoning: rebuild the best-known config from stored learnings."""
    champion = dict(NAIVE_DEFAULTS[channel])
    tested = set()
    for m in memory.all(kind="learning"):
        md = m["metadata"]
        if md.get("channel") != channel:
            continue
        champion[md["dimension"]] = md["winner"]
        tested.add((md["dimension"], md["loser"]))
        tested.add((md["dimension"], md["winner"]))
    return champion, tested


def plan(memory, channel: str, use_memory: bool, round_no: int) -> dict:
    dims = CHANNELS[channel]["dimensions"]
    rng = random.Random(f"{channel}-{round_no}-{use_memory}")

    if use_memory:
        champion, tested = _champion_from_memory(memory, channel)
        # challenger: change one dimension to a value we have NOT tested yet
        options = [(d, v) for d, vals in dims.items() for v in vals
                   if v != champion[d] and (d, v) not in tested]
        if not options:
            options = [(d, v) for d, vals in dims.items() for v in vals if v != champion[d]]
        dim, val = rng.choice(options)
        reason = (f"Kept proven winners from memory; testing `{dim}` = `{val}` "
                  f"against current `{champion[dim]}`.")
    else:
        # no memory: agent starts from the same naive guesses every time
        champion = dict(NAIVE_DEFAULTS[channel])
        dim = rng.choice(list(dims))
        val = rng.choice([v for v in dims[dim] if v != champion[dim]])
        reason = "No memory: starting from generic best practices."

    challenger = dict(champion)
    challenger[dim] = val
    return {"A": champion, "B": challenger, "tested_dimension": dim, "reason": reason}


def render_copy(channel: str, cfg: dict, brief: str, brand_name: str) -> str:
    """PLACEHOLDER copywriter. Future: LLM writes copy from cfg + build_llm_context()."""
    product = brief or "our new collection"
    if channel == "email":
        hooks = {
            "urgency": f"Last chance: {product} ends tonight",
            "question": f"Ready for {product}?",
            "number": f"3 reasons you'll love {product}",
            "curiosity": f"We made something just for you…",
        }
        offers = {"discount": "Take 20% off.", "free_shipping": "Free shipping, today only.",
                  "exclusive_access": "Members get early access.", "none": ""}
        subject = hooks[cfg["subject_hook"]]
        if cfg["personalization"] == "first_name":
            subject = "{first_name}, " + subject[0].lower() + subject[1:]
        if cfg["emoji"] == "yes":
            subject += " 🔥"
        return (f"**Subject:** {subject}\n\n"
                f"{offers[cfg['offer']]} {brand_name} · sent {cfg['send_time']}")
    hooks = {
        "product_shot": f"Meet {product}.",
        "question": f"Which one would you pick? 👀",
        "behind_the_scenes": f"How we made {product}, from start to finish",
        "ugc_testimonial": f"\"Obsessed with {product}\" (a real customer)",
    }
    ctas = {"shop_now": "Shop now →", "link_in_bio": "Link in bio.",
            "comment_to_win": "Comment 🙌 to win one!"}
    tags = "#smallbusiness #shoplocal #newdrop #musthave #trending #instagood" \
        if cfg["hashtags"] == "many" else "#shoplocal"
    return (f"**[{cfg['format'].replace('_', ' ')}]** {hooks[cfg['hook']]}\n\n"
            f"{ctas[cfg['cta']]} {tags} · posted {cfg['post_time']}")


# ---------------- 3. simulate ----------------
def simulate(channel: str, cfg: dict, seed: str) -> dict:
    """Simulated audience: hidden preferences + noise -> channel metrics."""
    score = sum(HIDDEN_PREFS[channel][d][v] for d, v in cfg.items())
    rng = random.Random(int(hashlib.md5(seed.encode()).hexdigest(), 16))
    base = CHANNELS[channel]["base"]
    out = {}
    for metric, b in base.items():
        lift = 2.718 ** (score * (0.6 if metric in ("open_rate", "reach") else 1.0))
        val = b * lift * rng.uniform(0.92, 1.08)
        out[metric] = round(val) if isinstance(b, int) else round(val, 4)
    return out


# ---------------- 4. learn ----------------
def learn(memory, channel: str, plan_: dict, results: dict, campaign_name: str) -> dict:
    """Compare A vs B and write the learning + updated playbook back to memory."""
    primary = CHANNELS[channel]["primary"]
    dim = plan_["tested_dimension"]
    a, b = results["A"][primary], results["B"][primary]
    winner_key = "B" if b > a else "A"
    winner_val = plan_[winner_key][dim]
    loser_val = plan_["B" if winner_key == "A" else "A"][dim]
    lift = (max(a, b) - min(a, b)) / max(min(a, b), 1e-9)

    text = (f"[{channel}] {dim}: '{winner_val}' beat '{loser_val}' "
            f"({primary} {max(a, b):.2%} vs {min(a, b):.2%}, +{lift:.0%}) in '{campaign_name}'. "
            f"Keep '{winner_val}' for {dim}.")
    learning = memory.add(text, {"kind": "learning", "channel": channel, "dimension": dim,
                                 "winner": winner_val, "loser": loser_val,
                                 "lift": round(lift, 4), "campaign": campaign_name})

    champion = plan_[winner_key]
    pb_text = f"[{channel}] Best-known config: " + ", ".join(f"{k}={v}" for k, v in champion.items())
    memory.add(pb_text, {"kind": "playbook", "channel": channel, "config": champion})
    return {"winner": winner_key, "lift": lift, "learning": learning["memory"]}
