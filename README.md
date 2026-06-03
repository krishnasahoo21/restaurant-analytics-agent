# 🍢 Restaurant Analytics AI Agent

> An intelligent analytics agent for Tunday Kababi, Gurgaon — built to answer 
> natural language business questions using real restaurant data, powered by 
> Anthropic's Claude with tool use.

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Anthropic](https://img.shields.io/badge/Anthropic-Claude_Sonnet_4.5-orange)
![Streamlit](https://img.shields.io/badge/Streamlit-UI-red)
![Status](https://img.shields.io/badge/Status-Active-green)

---

## 🎯 The Problem

Restaurant owners drown in Excel reports. Daily sales files, 
item-wise reports, online order exports from Swiggy and Zomato, 
raw material calculations — all sitting in separate spreadsheets, 
requiring hours of manual analysis to answer basic business questions.

**This agent turns that into a 10-second conversation.**

---

## 💬 What It Does

Ask questions in plain English. Get data-backed answers instantly.

```
"Which delivery platform should we focus on growing?"
→ Agent calls get_channel_performance() + compare_channels_across_months()
→ "Focus on Zomato — it grew 20% MoM while Swiggy declined 12.75%.
   However Swiggy customers have higher AOV (₹656 vs ₹579)..."

"How much mutton keema should we procure next month?"
→ Agent calls get_raw_ingredients()
→ "Procure ~20 KG based on April patterns, with 15-20% growth buffer
   given Zomato momentum. This is your hero ingredient — never run out."
```

---

## 🏗️ Architecture

```
User Question (natural language)
          ↓
    Claude Sonnet 4.5
    (reads question + tool schemas)
          ↓
    Decides which tools to call
          ↓
┌─────────────────────────────────────┐
│           Tool Belt (13 tools)      │
│                                     │
│  Sales      → get_monthly_kpis()    │
│               compare_months()      │
│                                     │
│  Menu       → get_top_items()       │
│               get_category_         │
│               performance()         │
│               get_low_performing_   │
│               items()               │
│                                     │
│  Channels   → get_channel_          │
│               performance()         │
│               compare_channels_     │
│               across_months()       │
│                                     │
│  Time       → get_daily_trends()    │
│               get_day_of_week_      │
│               analysis()            │
│               get_peak_hours()      │
│                                     │
│  Customers  → get_repeat_           │
│               customers()           │
│                                     │
│  Operations → get_material_         │
│               requirements()        │
│               get_raw_ingredients() │
└─────────────────────────────────────┘
          ↓
    Tool results fed back to Claude
          ↓
    Claude synthesises final answer
          ↓
    Grounded, data-backed response
```

---

## 📊 Data Sources

| File | Description | Records |
|------|-------------|---------|
| `item_master.xlsx` | Menu catalogue | 75 items |
| `Daily_Sales_Summary_*.xlsx` | Monthly KPI reports | March + April 2026 |
| `Enterprise_Menu_Mix_Report.xlsx` | Item-level sales with categories | 40 items |
| `Item_Wise_Enterprise_*.xlsx` | Daily item sales matrix | 410 records |
| `Online_Orders_Reports_*.xlsx` | Transaction-level Swiggy/Zomato | 652 order lines |

**Business logic integrated:**
- Material calculator — maps menu item sales → prepared dish KG requirements
- Raw ingredient calculator — maps prepared dish KGs → procurement quantities

---

## 🔑 Key Technical Decisions

**Raw Anthropic API over LangChain**
Built the agent loop from scratch using the raw Anthropic API rather than 
LangChain or other frameworks. This was deliberate — to deeply understand 
tool use mechanics, the agent loop pattern, and multi-turn conversation 
management before abstracting them away.

**Tool use pattern**
Each tool is a focused Python function returning a clean dictionary. 
Claude receives JSON schemas describing each tool and autonomously decides 
which ones to call based on the user's question — including chaining multiple 
tools when a question requires data from multiple sources.

**Data validation**
Cross-validated parsed data against known summary figures:
```
April summary net sales:  ₹2,91,829
Menu mix net revenue:     ₹2,91,829  ✅ exact match
Item wise gross revenue:  ₹3,15,355
Discount reconciliation:  ₹3,15,355 - ₹23,526 = ₹2,91,829  ✅
```

**Merged cell handling**
The online orders Excel uses merged cells across multi-item orders. 
Solved using pandas forward fill (ffill) on order-level columns, 
preserving item-level granularity while correctly propagating 
order metadata.

---

## 🚀 Getting Started

### Prerequisites
- Python 3.8+
- Anthropic API key (get one at console.anthropic.com)

### Installation

```bash
# Clone the repo
git clone https://github.com/krishnasahoo21/restaurant-analytics-agent.git
cd restaurant-analytics-agent

# Create virtual environment
python3 -m venv venv
source venv/bin/activate       # Mac/Linux
venv\Scripts\activate          # Windows

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### Add Your Data

Place your Excel files in the `data/` folder:
```
data/
├── item_master.xlsx
├── Daily_Sales_Summary_*.xlsx
├── Enterprise_Menu_Mix_Report.xlsx
├── Item_Wise_Enterprise_*.xlsx
└── Online_Orders_Reports_*.xlsx
```

### Run

```bash
# Streamlit UI (recommended)
streamlit run app.py

# Terminal CLI
python cli.py
```

---

## 📁 Project Structure

```
restaurant-analytics-agent/
├── data/                      ← Excel data files (not in repo)
├── src/
│   ├── __init__.py
│   ├── data_loader.py         ← loads + validates all data sources
│   ├── tools.py               ← 13 analytical tool functions
│   ← agent.py                 ← core agent loop + tool execution
│   └── prompts.py             ← system prompt + agent personality
├── app.py                     ← Streamlit web UI
├── cli.py                     ← terminal chat interface
├── .env.example               ← environment variable template
├── requirements.txt           ← Python dependencies
└── README.md
```

---

## 💡 Sample Questions

**Sales Analysis**
- What was the total revenue in April?
- How did April compare to March?
- What is our average order value?

**Menu Performance**
- What were the top 10 selling items?
- Which category drives the most revenue?
- Which items should we consider removing from the menu?

**Channel Analysis**
- How did Swiggy vs Zomato perform?
- Which platform has the highest average order value?
- Which channel grew the most month on month?

**Time Patterns**
- Which day of the week is busiest?
- What are our peak ordering hours?
- What was our best and worst day in April?

**Customer Insights**
- Who are our most loyal customers?
- What is our customer repeat rate?
- Who is our highest value customer?

**Kitchen Operations**
- How much mutton galawati kabab mixture do we need to prepare?
- What raw ingredients should we procure for next month?
- Which ingredient has the highest demand?

---

## 🧠 What I Learned

Building this project taught me the practical difference between 
**data science** and **AI engineering:**

- Data scientists ask "what does the data say?"
- AI engineers build systems that answer that question automatically

Key technical learnings:
- **Tool use pattern** — how LLMs autonomously decide which functions to call
- **Agent loop** — the while loop that drives multi-step reasoning
- **Real-world data engineering** — merged cells, metadata headers, 
  repeated rows, wide-to-long transformations
- **Grounding** — why tool-based agents produce reliable answers 
  while pure LLMs hallucinate
- **System prompts** — how constraints and personality shape agent behaviour

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM | Claude Sonnet 4.5 (Anthropic) |
| Agent Framework | Raw Anthropic API (no LangChain) |
| Data Processing | Pandas, OpenPyXL |
| UI | Streamlit |
| Charts | Plotly |
| Language | Python 3.12 |
| Version Control | Git + GitHub |

---

## 🔮 Future Improvements

- [ ] Add March item-wise data for month-on-month item comparison
- [ ] Integrate forecasting tool using historical trends
- [ ] Add chart generation tool — agent generates visuals on demand
- [ ] Rebuild tool layer using AWS Strands framework
- [ ] Add PDF report generation — weekly summary auto-export
- [ ] Expand to multiple restaurant locations

---

## 📄 License

MIT License — see LICENSE file for details.

---

## 👤 Author

Built by **Krishna** as a portfolio project demonstrating 
AI Engineering capabilities — specifically agentic AI with 
tool use, real-world data engineering, and production UI development.

*Transitioning from Data Science to AI Engineering.*

---

> *"I built the agent loop from scratch before using any framework — 
> because understanding what happens under the hood is what separates 
> engineers from framework users."*