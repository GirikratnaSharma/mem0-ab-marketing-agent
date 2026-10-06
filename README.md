# Mem0 A/B Marketing Agent

Buildathon project (The Gen Academy × Mem0 × SVAI, SF Tech Week, Oct 5 2026). Theme: **Agents for small businesses**.

A marketing agent that runs A/B tests on campaigns and **remembers what worked** using Mem0, so every new campaign starts from past learnings.

## Planned flow
1. **Onboarding:** brand info + business info → stored in Mem0
2. **Campaign:** agent generates Variant A / Variant B → run test
3. **Simulation:** simulated audience scores variants → metrics + learnings stored in Mem0
4. **Dashboard:** campaigns 1..N with performance
5. **New campaign:** agent uses remembered learnings to do better next time

## Team
- [@GirikratnaSharma](https://github.com/GirikratnaSharma)
- [@deepupai](https://github.com/deepupai)
- [@sakshamrai101](https://github.com/sakshamrai101)
- [@Ruta-U](https://github.com/Ruta-U)

## Memory (Mem0)
`memory.py` is the only file that talks to Mem0. Use `remember(business_id, exchange)` to store and `recall(business_id, query)` to read.

- `user_id` = one business (brand profile, what worked for them). Private to that business.
- `agent_id` = the marketing agent (general lessons). Shared across every business.

Setup:
```bash
pip install -r requirements.txt
cp .env.example .env          # add your MEM0_API_KEY
python setup_mem0.py          # once per Mem0 project: sets the extraction rules
python demo_memory.py         # business #2 recalls what business #1 learned
```
Keep raw metrics for the dashboard in the app's own store. Mem0 holds facts and lessons, not numbers.
