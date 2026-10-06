"""End-to-end memory demo: business #2 benefits from what business #1 learned.

Run setup_mem0.py once first, then: python demo_memory.py
"""
import time

from memory import list_memories, recall, remember, reset, wait_for_events

CAFE = "biz_sunrise_cafe"
BAKERY = "biz_golden_crust_bakery"

reset([CAFE, BAKERY])
time.sleep(10)  # let deletes settle before adding

# 1. Onboarding: the cafe's brand profile
events = [remember(CAFE, [
    {"role": "user", "content": "We're Sunrise Cafe, a neighborhood coffee shop in the Mission. "
                                "Our voice is warm and friendly, never pushy. Customers are "
                                "locals and remote workers. Goal: more weekday morning visits."},
    {"role": "assistant", "content": "Saved your brand profile: warm, friendly voice; locals and "
                                     "remote workers; goal is weekday morning traffic."}])]

# 2. Campaign + simulation result, with the lesson stated in plain words
events.append(remember(CAFE, [
    {"role": "user", "content": "The A/B test is done. Variant B, 'Your morning table is waiting', "
                                "beat Variant A, '20% off lattes'. General lesson: for local food "
                                "businesses, a personal, community feel beats a discount offer."},
    {"role": "assistant", "content": "Logged. Winner: Variant B, community framing. General lesson: "
                                     "for local food businesses, community framing beats discounts."}]))
wait_for_events(events)

print(f"Cafe's private shelf ({CAFE}):")
for m in list_memories(CAFE):
    print(f"   - {m['memory']}")
print("\nShared agent shelf:")
for m in list_memories():
    print(f"   - {m['memory']}")

# 3. A brand-new business, no history: its first campaign already gets the lesson
wait_for_events([remember(BAKERY, [
    {"role": "user", "content": "We're Golden Crust, a family bakery. Playful voice. "
                                "We want more weekend foot traffic."},
    {"role": "assistant", "content": "Saved your brand profile: playful voice; goal is weekend foot traffic."}])])

print(f"\nBakery's first campaign - what the agent recalls ({BAKERY}):")
for m in recall(BAKERY, "What messaging should our first campaign use?"):
    origin = "brand " if m.get("user_id") else "shared"
    print(f"   {m['score']:.2f}  [{origin}]  {m['memory']}")
