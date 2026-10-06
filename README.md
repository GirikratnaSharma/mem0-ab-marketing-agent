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

## Run it
```bash
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # add MEM0_API_KEY
.venv/bin/streamlit run app.py
```

## Code map
- `app.py`: Streamlit UI (Dashboard, New campaign, Onboarding, Memory)
- `agent.py`: agent loop `recall -> plan -> simulate -> learn`. Planning and copy are **placeholder rule-based logic**; `build_llm_context()` is where recalled Mem0 context will be re-fed into an LLM.
- `memory_store.py`: Mem0 Platform client + local JSON mirror/fallback

## How Mem0 is used
- **Onboarding** writes brand info and business info to Mem0 (`kind=brand`).
- **Before each campaign** the agent searches Mem0 for brand facts + past A/B learnings for that channel.
- **After each test** the learning (`'question' hook beat 'urgency', +23% CTR`) and the updated playbook are written back to Mem0, so the next campaign starts from what worked.
- **Memory ON vs OFF benchmark** on the dashboard shows the compounding effect.
