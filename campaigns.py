"""Campaign records (raw metrics live here, not in Mem0) and one full test round."""
import json
import uuid
from datetime import datetime

import agent
from memory_store import DATA_DIR

CAMPAIGNS_PATH = DATA_DIR / "campaigns.json"
PROFILE_PATH = DATA_DIR / "profiles.json"
DRAFTS_PATH = DATA_DIR / "drafts.json"


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


def delete_campaigns(user_id):
    save_json(CAMPAIGNS_PATH, [c for c in load_json(CAMPAIGNS_PATH, []) if c["user_id"] != user_id])


def _draft_key(user_id, channel):
    return f"{user_id}::{channel}"


def load_draft(user_id, channel):
    """The unlaunched plan for this business and channel, so a refresh doesn't lose it."""
    return load_json(DRAFTS_PATH, {}).get(_draft_key(user_id, channel))


def save_draft(user_id, channel, draft):
    drafts = load_json(DRAFTS_PATH, {})
    if draft is None:
        drafts.pop(_draft_key(user_id, channel), None)
    else:
        drafts[_draft_key(user_id, channel)] = draft
    save_json(DRAFTS_PATH, drafts)


def clear_drafts(user_id):
    save_json(DRAFTS_PATH, {k: v for k, v in load_json(DRAFTS_PATH, {}).items()
                            if not k.startswith(f"{user_id}::")})


def next_round(user_id, channel):
    return len([c for c in campaigns_for(user_id) if c["channel"] == channel]) + 1


def run_round(memory, user_id, channel, brief, name, use_memory=True,
              plan=None, strategy=None, source="autopilot", memories_used=None):
    """Simulate + learn for one campaign. Without a plan (Quick demo) the rule-based
    autopilot picks the test. Returns the saved campaign record."""
    round_no = next_round(user_id, channel)
    if plan is None:
        memories_used = len(agent.recall(memory, channel, brief)["learnings"])
        plan = agent.plan(memory, channel, use_memory, round_no)
    results = {k: agent.simulate(channel, plan[k], f"{user_id}-{channel}-{round_no}-{k}") for k in ("A", "B")}
    outcome = agent.learn(memory, channel, plan, results, name)
    primary = agent.CHANNELS[channel]["primary"]
    c = {
        "id": str(uuid.uuid4())[:8], "user_id": user_id, "name": name, "channel": channel,
        "brief": brief, "round": round_no, "plan": plan, "results": results,
        "winner": outcome["winner"], "lift": outcome["lift"], "tie": outcome["tie"],
        "learning": outcome["learning"],
        "primary": primary, "winner_score": results[outcome["winner"]][primary],
        "memories_used": memories_used or 0, "use_memory": use_memory,
        "strategy": strategy, "strategy_source": source,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    save_campaign(c)
    return c
