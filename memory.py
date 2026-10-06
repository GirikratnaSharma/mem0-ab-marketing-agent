"""Mem0 memory layer for the A/B marketing agent.

Two shelves of memory:
- user_id  = one small business: its brand profile and what worked for *it* (private)
- agent_id = the marketing agent: general lessons shared across *every* business

Every add carries both ids; Mem0 routes each extracted fact to the right shelf
using the rules set once in setup_mem0.py. Teammates should only need
remember() and recall().
"""
import os
import time
from typing import Optional

import requests
from dotenv import load_dotenv
from mem0 import MemoryClient

load_dotenv()

AGENT_ID = "ab_marketing_agent"
client = MemoryClient()  # reads MEM0_API_KEY from the environment

USER_RULES = """
Memory for a marketing agent that runs A/B tests on campaigns for small businesses.

STORE:
- The business's brand voice, products, target audience, goals and constraints
- Which variant won each test for this business, and why

IGNORE:
- Greetings, small talk, and filler
- Raw metric values and timestamps (they live in the app's own database)
"""

AGENT_RULES = """
These rules govern AGENT-scoped memories for the marketing agent, shared by every
business it works with.

STORE (useful for every business):
- Generalizable marketing lessons: which framing, tone, call to action or
  subject-line style tends to win, and for what kind of business or audience

IGNORE:
- Anything specific to one brand: names, products, prices, private details
- Raw metric values and timestamps
- Greetings, small talk, and filler
"""


def configure_project():
    """Set the extraction rules. Project-wide: run once, by one person (setup_mem0.py)."""
    client.project.update(custom_instructions=USER_RULES,
                          agent_custom_instructions=AGENT_RULES)


def remember(business_id: str, exchange: list[dict]) -> str:
    """Store one user/assistant exchange. Returns the add event id.

    Write the exchange in plain words; state general lessons explicitly
    (e.g. "General lesson: ...") so they land on the shared shelf.
    """
    return client.add(exchange, user_id=business_id, agent_id=AGENT_ID)["event_id"]


def recall(business_id: str, query: str) -> list[dict]:
    """This business's memories plus the shared lessons, each with a relevance score."""
    return client.search(query, filters={"OR": [{"user_id": business_id},
                                                {"agent_id": AGENT_ID}]})["results"]


def wait_for_events(event_ids, cap_s=240, poll_s=2):
    """Demo-only: block until extraction has finished so a following recall sees it.
    In the app, add is fire-and-forget. If this times out, just re-run."""
    headers = {"Authorization": f"Token {os.environ['MEM0_API_KEY']}"}
    urls = [f"https://api.mem0.ai/v1/event/{e}/" for e in event_ids]
    statuses = []
    for _ in range(0, cap_s, poll_s):
        statuses = [requests.get(u, headers=headers).json().get("status") for u in urls]
        if all(s in ("SUCCEEDED", "FAILED") for s in statuses):
            return statuses
        time.sleep(poll_s)
    raise TimeoutError(f"add events still pending after {cap_s}s: {statuses}")


def list_memories(business_id: Optional[str] = None) -> list[dict]:
    """Everything on one shelf: a business's (if given) or the shared agent shelf."""
    f = {"user_id": business_id} if business_id else {"agent_id": AGENT_ID}
    return client.get_all(filters={"AND": [f]}, page_size=50)["results"]


def reset(business_ids: list[str]):
    """Delete per record id. delete_all queues an async sweep that can wipe
    memories added right after it, so we avoid it."""
    for shelf in [*business_ids, None]:
        for m in list_memories(shelf):
            client.delete(memory_id=m["id"])
