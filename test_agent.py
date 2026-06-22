# test_agent.py
from src.data_loader import load_all_data
from src.agent import RestaurantAgent

# ── Load data and initialise agent ─────────────────────────────────────────
print("Loading data...")
data = load_all_data()
agent = RestaurantAgent(data)

print("\n" + "═"*60)
print("  AGENT TEST — with verbose tool logging")
print("═"*60)


# ── Test 1: Simple single-tool question ────────────────────────────────────
print("\n📌 Q1: Simple KPI question")
print("─"*60)
response = agent.chat(
    "What was the total revenue in April 2026?",
    verbose=True
)
print(f"\n💬 Answer: {response}")

# ── Test 2: Multi-tool question ────────────────────────────────────────────
print("\n📌 Q2: Multi-tool question")
print("─"*60)
response = agent.chat(
    "Which delivery platform should we focus on growing and why?",
    verbose=True
)
print(f"\n💬 Answer: {response}")

# ── Test 3: Memory test — follow-up question ───────────────────────────────
print("\n📌 Q3: Follow-up (memory test)")
print("─"*60)
response = agent.chat(
    "What about the top selling items — how do they relate to that?",
    verbose=True
)
print(f"\n💬 Answer: {response}")

# ── Test 4: Operations question ────────────────────────────────────────────
print("\n📌 Q4: Operations question")
print("─"*60)
response = agent.chat(
    "How much mutton keema should we procure for next month?",
    verbose=True
)
print(f"\n💬 Answer: {response}")