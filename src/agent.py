"""
agent.py
--------
Core agent loop for the Tunday Kababi analytics agent.

Architecture:
    User question
        ↓
    Claude (reads question + tool definitions)
        ↓
    Tool use decision (stop_reason = "tool_use")
        ↓
    We execute the tool
        ↓
    Result fed back to Claude
        ↓
    Claude decides: more tools or final answer?
        ↓
    Final answer (stop_reason = "end_turn")

Two operating modes:
    Local mode  (use_athena=False):
        Uses src/tools.py — reads from local Excel files
        Covers March and April 2026 only
        Good for: development, eval regression tests, offline use

    Athena mode (use_athena=True):
        Uses src/athena_tools.py — queries AWS Athena
        Covers Jul 2025 → May 2026 (13 months)
        Good for: production, client demos, full data access
        Requires: AWS_PROFILE=tunday in .env (local) or IAM role (Lambda)
"""

import json
from anthropic import Anthropic
from dotenv import load_dotenv

from src.prompts import SYSTEM_PROMPT

load_dotenv()


# ══════════════════════════════════════════════════════════════════════════
# TOOL DEFINITIONS — What Claude sees
# ══════════════════════════════════════════════════════════════════════════
# Two sets of definitions: LOCAL (original 14 tools) and ATHENA (new 14).
# The agent picks the right set based on use_athena flag at init time.
# Descriptions are written to guide a moderate-performing LLM clearly —
# specific, with examples, and with explicit "use this when" guidance.

LOCAL_TOOL_DEFINITIONS = [
    {
        "name": "get_monthly_kpis",
        "description": (
            "Returns key performance indicators for a specific month. "
            "Use this for questions about revenue, orders, average order "
            "value, discounts or overall performance for March or April."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "month": {
                    "type": "string",
                    "description": "Month to query — 'march' or 'april'"
                }
            },
            "required": ["month"]
        }
    },
    {
        "name": "compare_months",
        "description": (
            "Compares March and April 2026 performance side by side. "
            "Use this for questions about growth, trends, month-on-month "
            "changes or how the business is progressing over time."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_top_items",
        "description": (
            "Returns the top selling menu items ranked by revenue or "
            "quantity. Use this for questions about best sellers, "
            "popular items, or menu performance."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "n": {
                    "type": "integer",
                    "description": "Number of top items to return (default 10)"
                },
                "sort_by": {
                    "type": "string",
                    "enum": ["revenue", "quantity"],
                    "description": "Rank by 'revenue' or 'quantity' (default revenue)"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_category_performance",
        "description": (
            "Returns sales breakdown by food category — Kababs, Biryani, "
            "Breads, Combos, Rolls, Main Course. Use this for questions "
            "about which category performs best or category mix."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "month": {
                    "type": "string",
                    "description": "Month to query — 'march' or 'april'"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_low_performing_items",
        "description": (
            "Identifies underperforming menu items with low sales or "
            "low revenue. Use this for questions about menu optimisation, "
            "items to consider removing, or slow-moving items."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "revenue_threshold": {
                    "type": "number",
                    "description": "Flag items below this net revenue (default 5000)"
                },
                "qty_threshold": {
                    "type": "integer",
                    "description": "Flag items below this quantity (default 10)"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_channel_performance",
        "description": (
            "Returns performance metrics for each sales channel "
            "in a single month — Swiggy, Zomato, POS, Magic Pin. "
            "Use this when the question is about how a specific "
            "platform performed, platform revenue share, or channel "
            "breakdown for ONE month. "
            "Examples: 'How did Swiggy do?', 'What is Zomato revenue?', "
            "'Which platform leads?', 'How did Swiggy perform in April?'"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "month": {
                    "type": "string",
                    "description": "Month to query — 'march' or 'april'"
                }
            },
            "required": []
        }
    },
    {
        "name": "compare_channels_across_months",
        "description": (
            "Compares channel performance ACROSS months — shows "
            "March vs April side by side for each platform. "
            "Use this ONLY when the question asks about channel "
            "trends over time, growth or decline between months. "
            "Examples: 'Which channel grew the most?', "
            "'How did platforms change month on month?', "
            "'Is Swiggy growing or declining over time?'"
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_daily_trends",
        "description": (
            "Returns day-by-day revenue and quantity for April 2026. "
            "Use this for questions about daily patterns, best/worst days, "
            "or specific date performance."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_day_of_week_analysis",
        "description": (
            "Analyses which days of the week perform best on average. "
            "Use this for questions about weekday vs weekend performance, "
            "staffing planning or day-of-week patterns."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_peak_hours",
        "description": (
            "Analyses online order patterns by hour of day. "
            "Use this for questions about peak ordering times, "
            "staffing windows or kitchen preparation scheduling."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_repeat_customers",
        "description": (
            "Identifies customers who ordered more than once in April. "
            "Use this for questions about customer loyalty, repeat rate, "
            "or most valuable customers."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "min_orders": {
                    "type": "integer",
                    "description": "Minimum orders to qualify as repeat (default 2)"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_material_requirements",
        "description": (
            "Returns prepared dish quantities in KG needed based on "
            "April sales. Use this for kitchen planning, prep scheduling "
            "or questions about how much of each dish to prepare."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_raw_ingredients",
        "description": (
            "Returns raw ingredient quantities in KG needed for procurement. "
            "Use this for questions about purchasing, stock planning or "
            "what raw materials to order."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_item_daily_sales",
        "description": (
            "Returns day-by-day sales quantity for a specific menu item. "
            "Use this for questions about daily performance of a specific "
            "item, how many days an item sold above a certain quantity, "
            "best/worst days for a specific dish, or item-level daily trends. "
            "Supports partial name matching — 'Tunday Mutton' will find "
            "both 2 Pcs and 4 Pcs variants. "
            "Examples: 'How many days were more than 30 Galawati Kababs sold?', "
            "'What was the best day for Mughlai Paratha?', "
            "'How did Chicken Biryani sell day by day?'"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "item_name": {
                    "type": "string",
                    "description": "Full or partial menu item name to search for"
                },
                "threshold": {
                    "type": "integer",
                    "description": "Count days where quantity exceeded this value (default 0)"
                }
            },
            "required": ["item_name"]
        }
    }
]


ATHENA_TOOL_DEFINITIONS = [
    {
        "name": "get_monthly_kpis",
        "description": (
            "Returns key performance indicators for any month from "
            "July 2025 to May 2026. Use this for questions about revenue, "
            "orders, average order value, discounts, channel split, or "
            "overall performance for a specific month and year. "
            "Examples: 'How did October 2025 perform?', "
            "'What was revenue in January 2026?', "
            "'Show me April 2026 KPIs'"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "month": {
                    "type": "string",
                    "description": (
                        "Month name ('april', 'october') or number ('04', '10')"
                    )
                },
                "year": {
                    "type": "string",
                    "description": (
                        "4-digit year string. Default '2026'. "
                        "Use '2025' for July–December 2025 data."
                    )
                }
            },
            "required": ["month"]
        }
    },
    {
        "name": "get_category_performance",
        "description": (
            "Returns revenue and quantity breakdown by food super category "
            "— Kabab and Roasted, Biryani, Breads, Combos, Rolls, Main Course. "
            "Use this for questions about which food category performs best, "
            "category revenue share, or comparing category mix across months. "
            "Examples: 'Which category had highest sales in October?', "
            "'How did Biryani perform in July 2025?', "
            "'What is the category breakdown for December?'"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "month": {
                    "type": "string",
                    "description": "Month name or number"
                },
                "year": {
                    "type": "string",
                    "description": "4-digit year string (default '2026')"
                }
            },
            "required": ["month"]
        }
    },
    {
        "name": "get_channel_performance",
        "description": (
            "Returns sales channel performance — Swiggy, Zomato, POS, "
            "Magic Pin — for a given month. Optionally compares against "
            "a second month to show channel growth or decline. "
            "Use this for ALL channel questions: single month breakdown "
            "AND cross-month channel comparisons. "
            "Examples: 'How did Swiggy perform in April?', "
            "'Compare Zomato vs Swiggy in October 2025', "
            "'Which channel grew most from March to April?', "
            "'Is Swiggy growing over time?' — pass compare_month for trends."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "month": {
                    "type": "string",
                    "description": "Primary month to analyse"
                },
                "year": {
                    "type": "string",
                    "description": "Year for primary month (default '2026')"
                },
                "compare_month": {
                    "type": "string",
                    "description": (
                        "Optional. Second month to compare against. "
                        "Pass this when the question asks about channel trends, "
                        "growth, or month-on-month change. "
                        "Example: month='april', compare_month='march'"
                    )
                },
                "compare_year": {
                    "type": "string",
                    "description": (
                        "Year for the comparison month. "
                        "Default: same as year parameter."
                    )
                }
            },
            "required": ["month"]
        }
    },
    {
        "name": "get_discount_breakdown",
        "description": (
            "Returns discount analysis for a month — total discounts by "
            "channel, average discount per order, discount as % of revenue. "
            "Use this for questions about discount strategy, Swiggy discount "
            "amounts, discount rate changes, or how much is being given away. "
            "Examples: 'What discounts were given in April?', "
            "'What is the average Swiggy discount?', "
            "'How much did we discount in March vs April?', "
            "'What is the discount rate on Swiggy orders?'"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "month": {
                    "type": "string",
                    "description": "Month name or number"
                },
                "year": {
                    "type": "string",
                    "description": "4-digit year string (default '2026')"
                }
            },
            "required": ["month"]
        }
    },
    {
        "name": "get_top_items",
        "description": (
            "Returns top selling menu items for a month ranked by revenue "
            "or quantity. Optionally filtered to one food category. "
            "Use this for questions about best sellers, most popular items, "
            "top items within a category, or menu performance. "
            "Examples: 'What were the top 5 items in October?', "
            "'Best selling rolls in April', "
            "'Top items by quantity in July 2025', "
            "'Which Biryani items sold most?' — use category_filter='Biryani'"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "month": {
                    "type": "string",
                    "description": "Month name or number"
                },
                "year": {
                    "type": "string",
                    "description": "4-digit year string (default '2026')"
                },
                "n": {
                    "type": "integer",
                    "description": "Number of top items to return (default 10)"
                },
                "sort_by": {
                    "type": "string",
                    "enum": ["revenue", "quantity"],
                    "description": "Rank by 'revenue' or 'quantity' (default 'revenue')"
                },
                "category_filter": {
                    "type": "string",
                    "description": (
                        "Optional. Filter results to one category only. "
                        "Valid values: 'Kabab and Roasted', 'Biryani', "
                        "'Breads', 'Combos', 'Rolls', 'Main Course'. "
                        "Use when question asks about items within a "
                        "specific food category."
                    )
                }
            },
            "required": ["month"]
        }
    },
    {
        "name": "get_low_performing_items",
        "description": (
            "Identifies menu items with low sales or low revenue — "
            "candidates for menu optimisation or removal. "
            "Use this for questions about underperforming items, "
            "menu rationalisation, or which items are slow moving. "
            "Examples: 'Which items should we consider removing?', "
            "'What items have low sales in April?', "
            "'Show me underperforming menu items'"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "month": {
                    "type": "string",
                    "description": "Month name or number (default 'april')"
                },
                "year": {
                    "type": "string",
                    "description": "4-digit year string (default '2026')"
                },
                "revenue_threshold": {
                    "type": "number",
                    "description": "Flag items below this net revenue (default ₹5000)"
                },
                "qty_threshold": {
                    "type": "integer",
                    "description": "Flag items below this quantity sold (default 10)"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_daily_trends",
        "description": (
            "Returns day-by-day revenue and quantity for a specific month. "
            "Use this for questions about daily patterns, best or worst "
            "performing days, specific date performance, or daily peaks. "
            "Examples: 'Which days in April had highest sales?', "
            "'What was the worst day in October 2025?', "
            "'Show me daily revenue for July 2025', "
            "'What were the top 3 days in December?'"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "month": {
                    "type": "string",
                    "description": "Month name or number (default 'april')"
                },
                "year": {
                    "type": "string",
                    "description": "4-digit year string (default '2026')"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_day_of_week_analysis",
        "description": (
            "Analyses which days of the week perform best on average. "
            "Can analyse a specific month or aggregate across all months. "
            "Use this for staffing planning, understanding weekend vs "
            "weekday patterns, or recurring day-of-week insights. "
            "Examples: 'Which day of the week is busiest?', "
            "'Compare weekday vs weekend performance', "
            "'Best day of week for planning staff rosters'"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "month": {
                    "type": "string",
                    "description": (
                        "Optional. Filter to one month. "
                        "Leave blank to aggregate across all available months."
                    )
                },
                "year": {
                    "type": "string",
                    "description": "Optional. 4-digit year string."
                }
            },
            "required": []
        }
    },
    {
        "name": "get_peak_hours",
        "description": (
            "Analyses online order patterns by hour of day for a month. "
            "Use this for questions about peak ordering times, kitchen "
            "preparation scheduling, or staffing by time of day. "
            "Examples: 'When do most orders come in?', "
            "'What is the busiest hour for orders?', "
            "'Peak ordering window for kitchen planning', "
            "'What time should we start prep?'"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "month": {
                    "type": "string",
                    "description": "Month name or number (default 'april')"
                },
                "year": {
                    "type": "string",
                    "description": "4-digit year string (default '2026')"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_item_daily_sales",
        "description": (
            "Returns day-by-day sales quantity for a specific menu item. "
            "Supports partial name matching — 'Tunday Mutton' finds all "
            "variants (2 Pcs, 4 Pcs, Combo, Roll etc.) and aggregates them. "
            "Use this for daily performance of a specific dish, production "
            "planning by day, or threshold analysis. "
            "Examples: 'How did Chicken Biryani sell daily in April?', "
            "'How many days were more than 30 Galawati Kababs sold?', "
            "'Best day for Mughlai Paratha in October 2025', "
            "'Daily production plan for Tunday Mutton Kabab'"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "item_name": {
                    "type": "string",
                    "description": (
                        "Full or partial menu item name. "
                        "Partial matching supported — 'Galawati' finds all "
                        "Galawati Kabab variants across 2 Pcs, 4 Pcs, Combo."
                    )
                },
                "month": {
                    "type": "string",
                    "description": "Month name or number (default 'april')"
                },
                "year": {
                    "type": "string",
                    "description": "4-digit year string (default '2026')"
                },
                "threshold": {
                    "type": "integer",
                    "description": (
                        "Optional. Count days where quantity exceeded this. "
                        "Example: threshold=30 returns how many days sold >30 units."
                    )
                }
            },
            "required": ["item_name"]
        }
    },
    {
        "name": "get_repeat_customers",
        "description": (
            "Identifies customers who ordered more than once in a month. "
            "Use this for customer loyalty analysis, repeat order rate, "
            "or finding the most valuable returning customers. "
            "Examples: 'Who are our most loyal customers?', "
            "'What is our customer repeat rate in April?', "
            "'How many customers ordered more than twice?'"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "month": {
                    "type": "string",
                    "description": "Month name or number (default 'april')"
                },
                "year": {
                    "type": "string",
                    "description": "4-digit year string (default '2026')"
                },
                "min_orders": {
                    "type": "integer",
                    "description": "Minimum orders to qualify as repeat (default 2)"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_material_requirements",
        "description": (
            "Returns prepared dish quantities in KG needed for kitchen "
            "production based on actual sales for a month. "
            "Use this for kitchen prep planning, production scheduling, "
            "or understanding how much of each dish to prepare. "
            "Also returns piece counts per dish for detailed planning. "
            "Examples: 'How much Galawati Kabab mixture do we need?', "
            "'What are the kitchen prep requirements for October?', "
            "'How many KG of Biryani did we need in April?'"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "month": {
                    "type": "string",
                    "description": "Month name or number (default 'april')"
                },
                "year": {
                    "type": "string",
                    "description": "4-digit year string (default '2026')"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_raw_ingredients",
        "description": (
            "Returns raw ingredient quantities in KG needed for procurement "
            "based on actual monthly sales. Derived from recipe ratios. "
            "Use this for purchasing decisions, supplier orders, stock "
            "planning, or questions about raw material requirements. "
            "Examples: 'How much mutton keema should we order for April?', "
            "'What raw ingredients do we need for October?', "
            "'Procurement quantities for next month based on past sales'"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "month": {
                    "type": "string",
                    "description": "Month name or number (default 'april')"
                },
                "year": {
                    "type": "string",
                    "description": "4-digit year string (default '2026')"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_item_components",
        "description": (
            "Returns the base components of a menu item — what goes into "
            "a combo, how many pieces of each base item it contains, "
            "and which other SKUs share the same base component. "
            "Use this for questions about combo contents, ingredient "
            "breakdown of a dish, total pieces across all SKUs containing "
            "an ingredient, or production component mapping. "
            "Examples: 'What goes into the Happy Feast combo?', "
            "'Which items contain Tunday Mutton Galawati Kabab?', "
            "'How many pieces of Galawati are in the Kabab Combo?', "
            "'Show me all SKUs that use Chicken Korma'"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "item_name": {
                    "type": "string",
                    "description": (
                        "Full or partial item name to look up. "
                        "Partial matching supported — 'Galawati' finds all "
                        "items related to Galawati Kabab. "
                        "'Happy Feast' finds that specific combo."
                    )
                }
            },
            "required": ["item_name"]
        }
    },
]


# ── Tool Maps ──────────────────────────────────────────────────────────────

def _build_local_tool_map():
    from src.tools import (
        initialise_tools,
        get_monthly_kpis,
        compare_months,
        get_top_items,
        get_category_performance,
        get_low_performing_items,
        get_channel_performance,
        compare_channels_across_months,
        get_daily_trends,
        get_day_of_week_analysis,
        get_peak_hours,
        get_repeat_customers,
        get_material_requirements,
        get_raw_ingredients,
        get_item_daily_sales,
    )
    return initialise_tools, {
        "get_monthly_kpis":               get_monthly_kpis,
        "compare_months":                 compare_months,
        "get_top_items":                  get_top_items,
        "get_category_performance":       get_category_performance,
        "get_low_performing_items":       get_low_performing_items,
        "get_channel_performance":        get_channel_performance,
        "compare_channels_across_months": compare_channels_across_months,
        "get_daily_trends":               get_daily_trends,
        "get_day_of_week_analysis":       get_day_of_week_analysis,
        "get_peak_hours":                 get_peak_hours,
        "get_repeat_customers":           get_repeat_customers,
        "get_material_requirements":      get_material_requirements,
        "get_raw_ingredients":            get_raw_ingredients,
        "get_item_daily_sales":           get_item_daily_sales,
    }


def _build_athena_tool_map():
    from src.athena_tools import (
        get_monthly_kpis,
        get_category_performance,
        get_channel_performance,
        get_discount_breakdown,
        get_top_items,
        get_low_performing_items,
        get_daily_trends,
        get_day_of_week_analysis,
        get_peak_hours,
        get_item_daily_sales,
        get_repeat_customers,
        get_material_requirements,
        get_raw_ingredients,
        get_item_components,
    )
    return {
        "get_monthly_kpis":          get_monthly_kpis,
        "get_category_performance":  get_category_performance,
        "get_channel_performance":   get_channel_performance,
        "get_discount_breakdown":    get_discount_breakdown,
        "get_top_items":             get_top_items,
        "get_low_performing_items":  get_low_performing_items,
        "get_daily_trends":          get_daily_trends,
        "get_day_of_week_analysis":  get_day_of_week_analysis,
        "get_peak_hours":            get_peak_hours,
        "get_item_daily_sales":      get_item_daily_sales,
        "get_repeat_customers":      get_repeat_customers,
        "get_material_requirements": get_material_requirements,
        "get_raw_ingredients":       get_raw_ingredients,
        "get_item_components":       get_item_components,
    }


# ── The Agent Class ────────────────────────────────────────────────────────

class RestaurantAgent:
    """
    The core analytics agent for Tunday Kababi.

    Maintains conversation history across turns so the agent
    remembers context within a session.

    Usage (local mode — 2 months, no AWS needed):
        agent = RestaurantAgent(data)
        response = agent.chat("What were top selling items in April?")

    Usage (Athena mode — 13 months, AWS required):
        agent = RestaurantAgent(data, use_athena=True)
        response = agent.chat("How did October 2025 compare to July 2025?")

    Bench/experiment overrides:
        agent = RestaurantAgent(
            data,
            use_athena=True,
            model="claude-haiku-4-5",
            system_prompt=my_custom_prompt,
        )
    """

    def __init__(
        self,
        data:             dict,
        use_athena:       bool = False,
        # ── Bench overrides (all optional) ────────────────────────────
        model:            str  = "claude-sonnet-4-5",
        system_prompt:    str  = None,
        tool_definitions: list = None,
    ):
        """
        Initialise the agent.

        Args:
            data:             output of load_all_data() from data_loader.py
                              (still needed for local mode and business logic)
            use_athena:       if True, use Athena tools (13 months of data)
                              if False, use local tools (March + April only)
            model:            Claude model to use (bench override)
            system_prompt:    custom system prompt (bench override)
            tool_definitions: custom tool schemas (bench override)
        """
        self.client    = Anthropic()
        self.messages  = []
        self.data      = data
        self.model     = model
        self.use_athena = use_athena

        # ── System prompt ──────────────────────────────────────────────
        self.system_prompt = system_prompt or SYSTEM_PROMPT

        # ── Tool setup ─────────────────────────────────────────────────
        if use_athena:
            self.tool_map         = _build_athena_tool_map()
            self.tool_definitions = tool_definitions or ATHENA_TOOL_DEFINITIONS
            print("🤖 Restaurant Analytics Agent ready! [Athena mode — 13 months]")
        else:
            initialise_tools_fn, self.tool_map = _build_local_tool_map()
            initialise_tools_fn(data)
            self.tool_definitions = tool_definitions or LOCAL_TOOL_DEFINITIONS
            print("🤖 Restaurant Analytics Agent ready! [Local mode — Mar + Apr 2026]")

    def chat(self, user_message: str, verbose: bool = False) -> str:
        """
        Send a message to the agent and get a response.
        Handles the full agent loop internally.

        Args:
            user_message: the user's question in natural language
            verbose:      if True, prints tool calls as they happen

        Returns:
            agent's final answer as a string
        """
        self.messages.append({
            "role":    "user",
            "content": user_message
        })

        while True:

            response = self.client.messages.create(
                model      = self.model,
                max_tokens = 4096,
                system     = self.system_prompt,
                tools      = self.tool_definitions,
                messages   = self.messages
            )

            if response.stop_reason == "end_turn":
                final_answer = next(
                    block.text
                    for block in response.content
                    if hasattr(block, "text")
                )
                self.messages.append({
                    "role":    "assistant",
                    "content": response.content
                })
                return final_answer

            elif response.stop_reason == "tool_use":
                self.messages.append({
                    "role":    "assistant",
                    "content": response.content
                })

                tool_results = []

                for block in response.content:
                    if block.type != "tool_use":
                        continue

                    tool_name  = block.name
                    tool_input = block.input

                    if verbose:
                        print(f"\n🔧 Tool called: {tool_name}")
                        print(f"   Input: {json.dumps(tool_input, indent=2)}")

                    result = self._execute_tool(tool_name, tool_input)

                    if verbose:
                        preview = result[:200] + "..." if len(result) > 200 else result
                        print(f"   Result preview: {preview}")

                    tool_results.append({
                        "type":        "tool_result",
                        "tool_use_id": block.id,
                        "content":     result
                    })

                if not tool_results:
                    print(
                        f"⚠️  Warning: stop_reason was 'tool_use' but no "
                        f"tool_use blocks found. "
                        f"Block types: {[b.type for b in response.content]}"
                    )
                    return (
                        "I encountered an issue processing that question. "
                        "Could you please rephrase it?"
                    )

                self.messages.append({
                    "role":    "user",
                    "content": tool_results
                })

            else:
                return (
                    f"Unexpected stop reason: {response.stop_reason}. "
                    f"Please try again."
                )

    def _execute_tool(self, tool_name: str, tool_input: dict) -> str:
        """
        Executes a tool by name with given inputs.

        In local mode: calls the module-level execute_tool so the
        eval framework's monkey-patching of agent_module.execute_tool
        still works correctly for tool selection tests.

        In Athena mode: calls the Athena tool map directly since the
        eval framework doesn't patch Athena tool calls.
        """
        if not self.use_athena:
            # Route through module-level execute_tool so eval
            # framework monkey-patching intercepts the call
            import src.agent as _self_module
            return _self_module.execute_tool(tool_name, tool_input)

        # Athena mode — use Athena tool map directly
        if tool_name not in self.tool_map:
            return json.dumps({
                "error": (
                    f"Unknown tool '{tool_name}'. "
                    f"Available: {list(self.tool_map.keys())}"
                )
            })

        try:
            result = self.tool_map[tool_name](**tool_input)
            return json.dumps(result, default=str)
        except Exception as e:
            return json.dumps({
                "error": f"Tool '{tool_name}' failed: {str(e)}"
            })

    def reset(self):
        """Clear conversation history to start a fresh session."""
        self.messages = []
        print("🔄 Conversation history cleared.")


# ── Module-level execute_tool (kept for eval framework compatibility) ──────
# The eval framework patches agent_module.execute_tool directly.
# This wrapper stays here so existing eval tests don't break.

def execute_tool(tool_name: str, tool_input: dict) -> str:
    """
    Module-level execute_tool kept for backward compatibility
    with the eval framework's monkey-patching approach.
    """
    from src.tools import (
        get_monthly_kpis, compare_months, get_top_items,
        get_category_performance, get_low_performing_items,
        get_channel_performance, compare_channels_across_months,
        get_daily_trends, get_day_of_week_analysis, get_peak_hours,
        get_repeat_customers, get_material_requirements,
        get_raw_ingredients, get_item_daily_sales,
    )

    TOOL_MAP = {
        "get_monthly_kpis":               get_monthly_kpis,
        "compare_months":                 compare_months,
        "get_top_items":                  get_top_items,
        "get_category_performance":       get_category_performance,
        "get_low_performing_items":       get_low_performing_items,
        "get_channel_performance":        get_channel_performance,
        "compare_channels_across_months": compare_channels_across_months,
        "get_daily_trends":               get_daily_trends,
        "get_day_of_week_analysis":       get_day_of_week_analysis,
        "get_peak_hours":                 get_peak_hours,
        "get_repeat_customers":           get_repeat_customers,
        "get_material_requirements":      get_material_requirements,
        "get_raw_ingredients":            get_raw_ingredients,
        "get_item_daily_sales":           get_item_daily_sales,
    }

    if tool_name not in TOOL_MAP:
        return json.dumps({
            "error": f"Unknown tool '{tool_name}'"
        })
    try:
        result = TOOL_MAP[tool_name](**tool_input)
        return json.dumps(result, default=str)
    except Exception as e:
        return json.dumps({"error": f"Tool '{tool_name}' failed: {str(e)}"})


# ── Backward compatibility exports for eval framework ─────────────────────
# The eval framework imports TOOL_MAP and TOOL_DEFINITIONS directly from
# this module and monkey-patches execute_tool. These module-level names
# keep the existing 27 eval tests working without any changes.
TOOL_DEFINITIONS = LOCAL_TOOL_DEFINITIONS


def _get_local_tool_map() -> dict:
    """
    Returns the local tool map — imported lazily so that
    initialise_tools(data) can be called before tools are used.
    Called on first access via the TOOL_MAP proxy below.
    """
    from src.tools import (
        get_monthly_kpis,
        compare_months,
        get_top_items,
        get_category_performance,
        get_low_performing_items,
        get_channel_performance,
        compare_channels_across_months,
        get_daily_trends,
        get_day_of_week_analysis,
        get_peak_hours,
        get_repeat_customers,
        get_material_requirements,
        get_raw_ingredients,
        get_item_daily_sales,
    )
    return {
        "get_monthly_kpis":               get_monthly_kpis,
        "compare_months":                 compare_months,
        "get_top_items":                  get_top_items,
        "get_category_performance":       get_category_performance,
        "get_low_performing_items":       get_low_performing_items,
        "get_channel_performance":        get_channel_performance,
        "compare_channels_across_months": compare_channels_across_months,
        "get_daily_trends":               get_daily_trends,
        "get_day_of_week_analysis":       get_day_of_week_analysis,
        "get_peak_hours":                 get_peak_hours,
        "get_repeat_customers":           get_repeat_customers,
        "get_material_requirements":      get_material_requirements,
        "get_raw_ingredients":            get_raw_ingredients,
        "get_item_daily_sales":           get_item_daily_sales,
    }


class _LazyToolMap:
    """
    Proxy object that behaves like a dict but builds the tool map
    on first access. This ensures tools are imported AFTER
    initialise_tools(data) has been called by run_evaluation.py.

    The eval framework uses TOOL_MAP[tool_name] and
    tool_name not in TOOL_MAP — both are supported here.
    """
    def __init__(self):
        self._map = None

    def _load(self):
        if self._map is None:
            self._map = _get_local_tool_map()

    def __getitem__(self, key):
        self._load()
        return self._map[key]

    def __contains__(self, key):
        self._load()
        return key in self._map

    def keys(self):
        self._load()
        return self._map.keys()

    def values(self):
        self._load()
        return self._map.values()

    def items(self):
        self._load()
        return self._map.items()


TOOL_MAP = _LazyToolMap()
