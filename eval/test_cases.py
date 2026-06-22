"""
test_cases.py
-------------
Evaluation test cases for the Tunday Kababi Analytics Agent.

Three categories of tests:
    1. Data Quality Tests    — verify tool outputs are accurate
    2. Tool Selection Tests  — verify Claude picks right tools
    3. Response Quality Tests — verify LLM reasoning is sound
"""

# ══════════════════════════════════════════════════════════════════════
# CATEGORY 1 — DATA QUALITY TESTS
# These test whether tool functions return correct data.
# Deterministic — we know exact expected values from validation.
# ══════════════════════════════════════════════════════════════════════

DATA_QUALITY_TESTS = [
    {
        "test_id":     "DQ_001",
        "name":        "April net sales accuracy",
        "description": "Verify get_monthly_kpis returns correct April net sales",
        "tool":        "get_monthly_kpis",
        "input":       {"month": "april"},
        "field":       "net_sales",
        "expected":    291829,
        "tolerance":   0,        # exact match required
        "severity":    "critical" # if this fails, agent gives wrong numbers
    },
    {
        "test_id":     "DQ_002",
        "name":        "April total orders accuracy",
        "description": "Verify correct order count for April",
        "tool":        "get_monthly_kpis",
        "input":       {"month": "april"},
        "field":       "total_orders",
        "expected":    489,
        "tolerance":   0,
        "severity":    "critical"
    },
    {
        "test_id":     "DQ_003",
        "name":        "April AOV accuracy",
        "description": "Verify average order value calculation",
        "tool":        "get_monthly_kpis",
        "input":       {"month": "april"},
        "field":       "avg_order_value",
        "expected":    596.79,
        "tolerance":   0.01,     # allow 1 paisa rounding difference
        "severity":    "high"
    },
    {
        "test_id":     "DQ_004",
        "name":        "March net sales accuracy",
        "description": "Verify correct March net sales",
        "tool":        "get_monthly_kpis",
        "input":       {"month": "march"},
        "field":       "net_sales",
        "expected":    260672,
        "tolerance":   0,
        "severity":    "critical"
    },
    {
        "test_id":     "DQ_005",
        "name":        "Top item is Tunday Mutton Galawati 4 Pcs",
        "description": "Verify correct top item by revenue",
        "tool":        "get_top_items",
        "input":       {"n": 1, "sort_by": "revenue"},
        "field":       "items[0].item_name",
        "expected":    "Tunday Mutton Galawati Kabab- 4 Pcs",
        "tolerance":   None,     # string match
        "severity":    "high"
    },
    {
        "test_id":     "DQ_006",
        "name":        "April top channel is Zomato",
        "description": "Verify Zomato leads April revenue",
        "tool":        "get_channel_performance",
        "input":       {"month": "april"},
        "field":       "top_channel",
        "expected":    "Zomato",
        "tolerance":   None,
        "severity":    "high"
    },
    {
        "test_id":     "DQ_007",
        "name":        "Best day of week is Saturday",
        "description": "Verify Saturday has highest avg daily revenue",
        "tool":        "get_day_of_week_analysis",
        "input":       {},
        "field":       "best_day_of_week",
        "expected":    "Saturday",
        "tolerance":   None,
        "severity":    "medium"
    },
    {
        "test_id":     "DQ_008",
        "name":        "Peak hour window is 19-21",
        "description": "Verify peak ordering window",
        "tool":        "get_peak_hours",
        "input":       {},
        "field":       "peak_window",
        "expected":    "19:00 – 21:00",
        "tolerance":   None,
        "severity":    "medium"
    },
    {
        "test_id":     "DQ_009",
        "name":        "Paratha is highest material demand",
        "description": "Verify paratha requires most KGs",
        "tool":        "get_material_requirements",
        "input":       {},
        "field":       "highest_demand",
        "expected":    "paratha",
        "tolerance":   None,
        "severity":    "medium"
    },
    {
        "test_id":     "DQ_010",
        "name":        "Online order platform count",
        "description": "Verify exactly 2 platforms in online orders",
        "tool":        "get_channel_performance",
        "input":       {"month": "april"},
        "field":       "channels_count",
        "expected":    4,        # Swiggy, Zomato, POS, Magic Pin
        "tolerance":   0,
        "severity":    "medium"
    },
]


# ══════════════════════════════════════════════════════════════════════
# CATEGORY 2 — TOOL SELECTION TESTS
# These test whether Claude picks the right tool(s) for each question.
# We check which tools were called — not just the final answer.
# ══════════════════════════════════════════════════════════════════════

TOOL_SELECTION_TESTS = [
    {
        "test_id":        "TS_001",
        "name":           "Revenue question triggers KPI tool",
        "question":       "What was the total revenue in April?",
        "expected_tools": ["get_monthly_kpis"],
        "forbidden_tools": [],   # tools that should NOT be called
        "severity":       "critical"
    },
    {
        "test_id":        "TS_002",
        "name":           "Channel question triggers channel tool",
        "question":       "How did Swiggy perform compared to Zomato?",
        "expected_tools": [
            "get_channel_performance",
            "compare_channels_across_months"  # either is acceptable
        ],
        "forbidden_tools": [],
        "any_of":         True,    # ← pass if EITHER tool called
        "severity":       "high"
    },
    {
        "test_id":        "TS_003",
        "name":           "MoM question triggers compare tool",
        "question":       "How did April compare to March?",
        "expected_tools": ["compare_months"],
        "forbidden_tools": [],
        "severity":       "high"
    },
    {
        "test_id":        "TS_004",
        "name":           "Top items question triggers menu tool",
        "question":       "What were the best selling items?",
        "expected_tools": ["get_top_items"],
        "forbidden_tools": [],
        "severity":       "high"
    },
    {
        "test_id":        "TS_005",
        "name":           "Channel strategy triggers multiple tools",
        "question":       "Which channel should we focus on and why?",
        "expected_tools": [
            "get_channel_performance",
            "compare_channels_across_months"
        ],
        "forbidden_tools": [],
        "severity":       "medium",
        "multi_tool":     True   # expects Claude to chain tools
    },
    {
        "test_id":        "TS_006",
        "name":           "Procurement question triggers operations tool",
        "question":       "How much mutton keema should we order?",
        "expected_tools": ["get_raw_ingredients"],
        "forbidden_tools": [],
        "severity":       "high"
    },
    {
        "test_id":        "TS_007",
        "name":           "Customer loyalty triggers repeat customer tool",
        "question":       "Who are our most loyal customers?",
        "expected_tools": ["get_repeat_customers"],
        "forbidden_tools": [],
        "severity":       "medium"
    },
    {
        "test_id":        "TS_008",
        "name":           "Peak hours question triggers time tool",
        "question":       "When do most orders come in?",
        "expected_tools": ["get_peak_hours"],
        "forbidden_tools": [],
        "severity":       "medium"
    },
    {
        "test_id":        "TS_009",
        "name":           "Out of scope question uses no tools",
        "question":       "What is the weather in Gurgaon today?",
        "expected_tools": [],    # Claude should answer without tools
        "forbidden_tools": ["get_monthly_kpis", "get_top_items"],
        "severity":       "medium"
    },
    {
        "test_id":        "TS_010",
        "name":           "Menu optimisation triggers low performing tool",
        "question":       "Which items should we consider removing?",
        "expected_tools": ["get_low_performing_items"],
        "forbidden_tools": [],
        "severity":       "medium"
    },
]


# ══════════════════════════════════════════════════════════════════════
# CATEGORY 3 — RESPONSE QUALITY TESTS
# These use LLM-as-Judge to evaluate reasoning quality.
# A second Claude instance reads the answer and rates it.
# ══════════════════════════════════════════════════════════════════════

RESPONSE_QUALITY_TESTS = [
    {
        "test_id":   "RQ_001",
        "name":      "Revenue answer is grounded in data",
        "question":  "What was April revenue?",
        "criteria": [
            "mentions the correct net sales figure (₹2,91,829)",
            "distinguishes gross revenue from net sales",
            "does not fabricate any numbers",
        ],
        "severity":  "critical"
    },
    {
        "test_id":   "RQ_002",
        "name":      "Channel recommendation is actionable",
        "question":  "Which delivery platform should we focus on?",
        "criteria": [
            "gives a clear recommendation (not just describes data)",
            "supports recommendation with specific numbers",
            "mentions both Swiggy and Zomato",
            "includes actionable next steps",
        ],
        "severity":  "high"
    },
    {
        "test_id":   "RQ_003",
        "name":      "Hallucination check — no invented numbers",
        "question":  "What was our customer retention rate in April?",
        "criteria": [   
            "does not invent numbers that weren't returned by tools",
            "if it mentions a retention rate, it should come from repeat customer data",
            "acknowledges if exact metric is not available",
        ],
        "severity":  "critical"
    },
    {
        "test_id":   "RQ_004",
        "name":      "Out of scope handled gracefully",
        "question":  "What will our revenue be in June 2027?",
        "criteria": [
            "does not make up specific revenue predictions",
            "clearly states the limitation",
            "offers what it CAN help with instead",
        ],
        "severity":  "high"
    },
    {
        "test_id":   "RQ_005",
        "name":      "Operations answer includes business context",
        "question":  "How much mutton keema should we procure?",
        "criteria": [
            "gives a specific quantity in KG",
            "mentions growth buffer or caveat",
            "connects answer to Galawati Kabab as hero product",
        ],
        "severity":  "medium"
    },
    {
        "test_id":   "RQ_006",
        "name":      "Comparison answer covers both months",
        "question":  "How did April compare to March?",
        "criteria": [
            "mentions both March and April figures",
            "calculates or mentions growth percentage",
            "highlights at least one specific insight",
        ],
        "severity":  "high"
    },
    {
        "test_id":   "RQ_007",
        "name":      "Answer tone is professional",
        "question":  "What were top selling items?",
        "criteria": [
            "response is professional and clear",
            "uses Indian Rupee symbol (₹) for amounts",
            "does not use unnecessary filler phrases",
        ],
        "severity":  "low"
    },
]