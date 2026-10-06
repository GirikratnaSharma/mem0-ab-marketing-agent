"""One-time setup: apply the extraction rules to the team's Mem0 project.

The rules are project-wide, so only one person needs to run this
(re-run it after editing USER_RULES / AGENT_RULES in memory.py).
"""
from memory import configure_project

if __name__ == "__main__":
    configure_project()
    print("Mem0 project configured: per-business rules + shared agent rules.")
