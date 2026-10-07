# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Small-business owners who do their own marketing: the owner of a martial-arts school, café, bakery or shop who writes their own email and Instagram posts between running the business, with no marketing team and no analytics background. Their job: decide what to send or post next, ship it quickly, and learn whether it worked, without having to remember or interpret past results themselves.

Agencies, freelancers, and demo audiences (judges, investors) are not the design target. The app supports switching between businesses (Business ID), but that exists for demos and testing, not as a confirmed agency workflow.

## Product Purpose

Campaign Lab is a marketing agent that runs A/B tests on a small business's campaigns and remembers what worked. Before every campaign it recalls past results, recommends one new idea to test against the proven setup, and writes both variants. After the test it stores the lesson, so the next campaign starts smarter.

Success: the owner's primary metric (email click-through, Instagram engagement) climbs campaign over campaign, and the owner can say *why* in plain words ("question subject lines beat urgency for us").

## Positioning

Three claims, in this order of weight:

1. **It remembers what worked (core mechanism).** Every A/B result becomes a memory (Mem0). Each new campaign keeps proven winners and tests exactly one new idea, so results compound instead of restarting from generic best practice. The Memory ON vs OFF benchmark demonstrates this.
2. **It learns across businesses.** General lessons from one business (e.g. "for local food businesses, community framing beats discounts") are stored on a shared agent shelf, so a brand-new business benefits from day one while each business's own brand and results stay private.
3. **Zero setup.** The owner pastes a website and Instagram handle and gets a brand profile and brand kit (voice, audience, colors, fonts, logo) that every campaign then uses.

## Operating Context

- Buildathon origin: The Gen Academy × Mem0 × SVAI, SF Tech Week, Oct 5 2026, theme "Agents for small businesses". Team: @GirikratnaSharma, @deepupai, @sakshamrai101, @Ruta-U.
- Workflow: Brand profile import → Create campaign (brief → AI strategy → preview A/B → launch) → results and saved lesson → Overview of performance and learnings → next campaign.
- Channels today: email and Instagram, each with fixed testable dimensions (email: subject hook, offer, personalization, emoji, send time; Instagram: format, hook, CTA, hashtags, post time).

## Capabilities and Constraints

- Streamlit (Python) web app; memory via Mem0 Platform with a local JSON fallback; AI strategist via the Claude API (`claude-opus-5-5`, structured output), with an offline rule-based strategist when no valid key is set.
- **Results are simulated today.** A simulated audience with hidden preferences scores the variants. **Real sends are planned next** (email and Instagram integrations). Until then the product must label results as simulated and never imply real sends or real customer metrics. Design so real metrics can replace simulated ones without restructuring.
- Brand import is simulated too: canned scrape fixtures, no live scraping.
- Cross-business learning exists in `memory.py` (user and agent shelves, `remember()`/`recall()`) and the `demo_memory.py` script, but the app's memory adapter does not route through the shared shelf yet (open TODO).
- Raw metrics live in the app's campaign store; Mem0 holds facts and lessons, not numbers.
- Undecided: which real email / Instagram providers come first, and pricing or business model.

## Brand Commitments

- Product name in the UI: "Campaign Lab" (repo: `mem0-ab-marketing-agent`). Not yet confirmed as the final product name.
- The app renders each business's own brand (logo, colors, voice) in variant previews; the product's chrome stays neutral around it.

## Evidence on Hand

- Demo business: Kung Fu Kids® (@wushucentral), scrape fixtures in `data/business-onboarding/` (website.json, instagram.json).
- Memory ON vs OFF benchmark (simulated) in the Overview page.
- No real customers, testimonials, real campaign metrics, or press. Do not fabricate any.

## Product Principles

1. **One idea per test.** Variant B changes exactly one thing from the proven setup, so every result teaches something attributable.
2. **Show the evidence behind every recommendation.** The strategist cites the past results it is building on; the owner can always see why.
3. **Plain words for a busy owner.** Lessons and recommendations read as sentences a non-marketer can act on, not dashboards to interpret.
4. **Honest about what's real.** Simulated results and imported data are labeled as such until real integrations exist.
5. **Memory compounds.** Every screen should make it clear that today's campaign builds on the last one.
