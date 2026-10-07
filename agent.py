"""A/B testing marketing agent.

Loop per campaign round:
  1. recall()      -> pull brand facts + past learnings for this channel from memory
  2. plan          -> Variant A = current champion (built from learnings),
                      Variant B = champion with ONE dimension changed (challenger).
                      strategist.suggest() lets the LLM pick the challenger from
                      test_options() and write the copy; plan() is the fast
                      rule-based autopilot used by Quick demo and the benchmark.
  3. simulate()    -> simulated audience returns channel metrics
  4. learn()       -> compare A vs B, write the learning + updated playbook back to memory
"""
import hashlib
import random
import re

# ---------------- channel config ----------------
CHANNELS = {
    "email": {
        "dimensions": {
            "subject_hook": ["urgency", "question", "number", "curiosity"],
            "offer": ["discount", "free_trial", "bring_a_friend", "none"],
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
            "hook": ["showcase", "question", "behind_the_scenes", "customer_quote"],
            "cta": ["book_now", "link_in_bio", "comment_to_win"],
            "hashtags": ["many", "few"],
            "post_time": ["morning", "evening"],
        },
        "metrics": ["reach", "engagement_rate", "saves", "ctr"],
        "primary": "engagement_rate",
        "base": {"reach": 4000, "engagement_rate": 0.03, "saves": 40, "ctr": 0.008},
    },
}

# Hidden audience preferences: the "ground truth" the agent has to discover.
# Obvious defaults (discount, emoji, plain showcase shots, hashtag spam) are deliberately mediocre.
HIDDEN_PREFS = {
    "email": {
        "subject_hook": {"urgency": -0.05, "question": 0.25, "number": 0.10, "curiosity": 0.15},
        "offer": {"discount": 0.0, "free_trial": 0.12, "bring_a_friend": 0.30, "none": -0.15},
        "personalization": {"first_name": 0.20, "none": 0.0},
        "emoji": {"yes": -0.05, "no": 0.05},
        "send_time": {"morning": 0.12, "evening": 0.0},
    },
    "instagram": {
        "format": {"single_image": 0.0, "carousel": 0.20, "reel": 0.35},
        "hook": {"showcase": 0.0, "question": 0.10, "behind_the_scenes": 0.30, "customer_quote": 0.22},
        "cta": {"book_now": 0.0, "link_in_bio": 0.05, "comment_to_win": 0.25},
        "hashtags": {"many": -0.08, "few": 0.08},
        "post_time": {"morning": 0.0, "evening": 0.15},
    },
}

NAIVE_DEFAULTS = {
    "email": {"subject_hook": "urgency", "offer": "discount", "personalization": "none",
              "emoji": "yes", "send_time": "evening"},
    "instagram": {"format": "single_image", "hook": "showcase", "cta": "book_now",
                  "hashtags": "many", "post_time": "morning"},
}


# Plain-language names, written to read in "Try X instead of Y" and "X beat Y".
OPTION_LABELS = {
    "email": {
        "subject_hook": {"urgency": "an urgent subject line", "question": "a question subject line",
                         "number": "a numbered subject line", "curiosity": "a curiosity subject line"},
        "offer": {"discount": "a discount", "free_trial": "a free first visit",
                  "bring_a_friend": "a bring-a-friend offer", "none": "no offer"},
        "personalization": {"first_name": "greeting readers by first name", "none": "a generic greeting"},
        "emoji": {"yes": "an emoji in the subject", "no": "a plain subject"},
        "send_time": {"morning": "sending in the morning", "evening": "sending in the evening"},
    },
    "instagram": {
        "format": {"single_image": "a single photo", "carousel": "a carousel", "reel": "a reel"},
        "hook": {"showcase": "a straight showcase", "question": "an opening question",
                 "behind_the_scenes": "a behind-the-scenes look", "customer_quote": "a customer quote"},
        "cta": {"book_now": "\u201cBook now\u201d", "link_in_bio": "\u201cLink in bio\u201d",
                "comment_to_win": "a comment-to-win giveaway"},
        "hashtags": {"many": "lots of hashtags", "few": "one or two hashtags"},
        "post_time": {"morning": "posting in the morning", "evening": "posting in the evening"},
    },
}

DIMENSION_LABELS = {
    "subject_hook": "subject line", "offer": "offer", "personalization": "greeting", "emoji": "emoji",
    "send_time": "send time", "format": "post format", "hook": "opening", "cta": "call to action",
    "hashtags": "hashtags", "post_time": "post time",
}

METRIC_LABELS = {"open_rate": "Opens", "ctr": "Click-through", "conversion_rate": "Sign-ups",
                 "reach": "Reach", "engagement_rate": "Engagement", "saves": "Saves"}

METRIC_HELP = {"open_rate": "share of people who opened it", "ctr": "share who clicked",
               "conversion_rate": "share who signed up", "reach": "people who saw it",
               "engagement_rate": "share who liked, commented or shared", "saves": "people who saved it"}

# Below this relative difference the simulated audience's noise can explain the gap.
TIE_LIFT = 0.05


def option_label(channel: str, dim: str, value: str) -> str:
    return OPTION_LABELS[channel][dim].get(value, value.replace("_", " "))


def describe_change(channel: str, dim: str, old: str, new: str) -> str:
    return f"Try {option_label(channel, dim, new)} instead of {option_label(channel, dim, old)}."


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]


# ---------------- 1. recall ----------------
def recall(memory, channel: str, brief: str) -> dict:
    """Pull brand info + past learnings for this channel."""
    brand = memory.search(f"brand voice business audience {brief}", filters={"kind": "brand"}, top_k=5)
    learnings = memory.search(f"{channel} A/B test learnings what worked {brief}",
                              filters={"kind": "learning", "channel": channel}, top_k=10)
    playbook = [m for m in memory.all(kind="playbook") if m["metadata"].get("channel") == channel]
    return {"brand": brand, "learnings": learnings, "playbook": playbook[-1] if playbook else None}


# ---------------- 2. plan ----------------
def _champion_from_memory(memory, channel: str) -> tuple[dict, set]:
    """Rebuild the best-known config from stored learnings (later learnings win)."""
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


# Offers an owner can name in a brief; when the brief names one it is locked, not tested.
OFFER_WORDS = {"free_trial": ("free trial", "free class", "first class free", "free first", "free lesson",
                              "trial class", "first visit free", "free visit"),
               "bring_a_friend": ("bring a friend", "bring-a-friend", "refer a friend"),
               "discount": ("% off", "percent off", "discount", "sale")}


def brief_locks(channel: str, brief: str) -> dict:
    """Settings the brief already decides, e.g. an offer it names. Kept in both versions."""
    text = (brief or "").lower()
    if channel != "email":
        return {}
    for value, words in OFFER_WORDS.items():
        if any(w in text for w in words):
            return {"offer": value}
    return {}


def test_options(memory, channel: str, use_memory: bool = True, locks: dict | None = None) -> tuple[dict, list]:
    """The champion config (Variant A) and every single-dimension change worth testing.
    With memory, already-tested values are skipped until everything has been tried.
    Locked settings (from the brief) are applied to A and never tested."""
    dims = CHANNELS[channel]["dimensions"]
    locks = locks or {}
    if use_memory:
        champion, tested = _champion_from_memory(memory, channel)
    else:
        champion, tested = dict(NAIVE_DEFAULTS[channel]), set()
    champion.update(locks)
    free = {d: vals for d, vals in dims.items() if d not in locks}
    options = [(d, v) for d, vals in free.items() for v in vals if v != champion[d] and (d, v) not in tested]
    if not options:
        options = [(d, v) for d, vals in free.items() for v in vals if v != champion[d]]
    return champion, options


def make_plan(champion: dict, dim: str, val: str, reason: str) -> dict:
    challenger = dict(champion)
    challenger[dim] = val
    return {"A": dict(champion), "B": challenger, "tested_dimension": dim, "reason": reason}


def plan(memory, channel: str, use_memory: bool, round_no: int) -> dict:
    """Rule-based autopilot: random untested challenger, no LLM call."""
    dims = CHANNELS[channel]["dimensions"]
    rng = random.Random(f"{channel}-{round_no}-{use_memory}")

    if use_memory:
        champion, options = test_options(memory, channel)
        dim, val = rng.choice(options)
        reason = (f"Kept proven winners from memory; testing `{dim}` = `{val}` "
                  f"against current `{champion[dim]}`.")
    else:
        # no memory: agent starts from the same naive guesses every time
        champion = dict(NAIVE_DEFAULTS[channel])
        dim = rng.choice(list(dims))
        val = rng.choice([v for v in dims[dim] if v != champion[dim]])
        reason = "No memory: starting from generic best practices."

    return make_plan(champion, dim, val, reason)


def short_topic(brief: str, max_words: int = 6) -> str:
    """A short noun phrase for template copy: the brief's first clause, at most a few words."""
    first = re.split(r"[:.;!?\n\u2014\u2013]|,| - ", brief or "")[0].strip()
    words = first.split()
    if not words or len(words) > max_words:  # a long sentence, not a name: don't cut it mid-thought
        return "What's new"
    phrase = " ".join(words[:max_words]).rstrip(",.;:-")
    return phrase[:1].upper() + phrase[1:]


def template_copy(channel: str, cfg: dict, brief: str, brand_name: str) -> dict:
    """Offline copywriter used when no LLM is available. Same shape as the
    strategist's VariantCopy: headline, body, cta, visual."""
    topic = short_topic(brief)
    low = topic[:1].lower() + topic[1:]
    if channel == "email":
        hooks = {
            "urgency": f"Last call: {low}",
            "question": f"Ready for {low}?",
            "number": f"3 reasons not to miss {low}",
            "curiosity": "Something new is starting at " + brand_name,
        }
        offers = {"discount": "Members save 20% on their first month.",
                  "free_trial": "Your first visit is on us.",
                  "bring_a_friend": "Bring a friend and you both get a free week.", "none": ""}
        subject = hooks[cfg["subject_hook"]]
        if cfg["personalization"] == "first_name":
            subject = "{first_name}, " + subject[0].lower() + subject[1:]
        if cfg["emoji"] == "yes":
            subject += " \U0001F525"
        body = f"{topic} at {brand_name}. Spots are limited, so save yours early. {offers[cfg['offer']]}".strip()
        return {"headline": subject, "body": body, "cta": "Save my spot",
                "visual": f"Your people in action at {brand_name}"}
    hooks = {
        "showcase": f"{topic} at {brand_name}.",
        "question": "What would you try first?",
        "behind_the_scenes": f"Behind the scenes: getting ready for {low}",
        "customer_quote": "\u201cBest decision we made this year\u201d (one of our families)",
    }
    ctas = {"book_now": "Book now.", "link_in_bio": "Link in bio.",
            "comment_to_win": "Comment below to win a free week!"}
    tags = ("#smallbusiness #supportlocal #community #family #newseason #local"
            if cfg["hashtags"] == "many" else "#supportlocal")
    fmt = {"single_image": "Photo", "carousel": "Carousel", "reel": "Reel"}[cfg["format"]]
    return {"headline": hooks[cfg["hook"]], "body": tags, "cta": ctas[cfg["cta"]],
            "visual": f"{topic} at {brand_name}"}


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
    """Compare A vs B and write the learning + updated playbook back to memory.
    A difference under TIE_LIFT is recorded as too close to call and the champion stays."""
    primary = CHANNELS[channel]["primary"]
    metric = METRIC_LABELS[primary].lower()
    dim = plan_["tested_dimension"]
    a, b = results["A"][primary], results["B"][primary]
    lift = (max(a, b) - min(a, b)) / max(min(a, b), 1e-9)
    tie = lift < TIE_LIFT
    winner_key = "A" if tie or a >= b else "B"
    winner_val = plan_[winner_key][dim]
    loser_val = plan_["B" if winner_key == "A" else "A"][dim]
    win, lose = option_label(channel, dim, winner_val), option_label(channel, dim, loser_val)

    if tie:
        text = (f"On {channel}, {lose} and {win} performed about the same (within {TIE_LIFT:.0%} on "
                f"{metric}). Too close to call, so we keep {win}.")
    else:
        text = f"On {channel}, {win} beat {lose} (+{lift:.0%} {metric}). Keep {win}."
    learning = memory.add(text, {"kind": "learning", "channel": channel, "dimension": dim,
                                 "winner": winner_val, "loser": loser_val, "tie": tie,
                                 "lift": round(lift, 4), "campaign": campaign_name})

    champion = plan_[winner_key]
    pb_text = f"[{channel}] Best-known config: " + ", ".join(f"{k}={v}" for k, v in champion.items())
    memory.add(pb_text, {"kind": "playbook", "channel": channel, "config": champion})
    return {"winner": winner_key, "lift": lift, "tie": tie, "learning": learning["memory"]}
