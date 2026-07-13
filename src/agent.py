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

This loop is the fundamental pattern of all LLM agents.
"""

import json
from anthropic import Anthropic
from dotenv import load_dotenv

from src.prompts import SYSTEM_PROMPT
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
    get_item_daily_sales 
)

load_dotenv()


# ── Tool Definitions ───────────────────────────────────────────────────────
# These JSON schemas tell Claude what each tool does and what
# parameters it accepts. This is how Claude knows WHEN and HOW
# to call each tool. The descriptions are critical — Claude reads
# them to decide which tool fits the user's question.

TOOL_DEFINITIONS = [
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


# ── Tool Executor ──────────────────────────────────────────────────────────
# Maps tool names to actual Python functions
# When Claude says "call get_top_items", this is how we know
# which function to actually run

TOOL_MAP = {
    "get_monthly_kpis":              get_monthly_kpis,
    "compare_months":                compare_months,
    "get_top_items":                 get_top_items,
    "get_category_performance":      get_category_performance,
    "get_low_performing_items":      get_low_performing_items,
    "get_channel_performance":       get_channel_performance,
    "compare_channels_across_months":compare_channels_across_months,
    "get_daily_trends":              get_daily_trends,
    "get_day_of_week_analysis":      get_day_of_week_analysis,
    "get_peak_hours":                get_peak_hours,
    "get_repeat_customers":          get_repeat_customers,
    "get_material_requirements":     get_material_requirements,
    "get_raw_ingredients":           get_raw_ingredients,
    "get_item_daily_sales":          get_item_daily_sales
}


def execute_tool(tool_name: str, tool_input: dict) -> str:
    """
    Executes a tool by name with given inputs.
    Returns result as a JSON string for Claude to read.

    Args:
        tool_name:  name of the tool to execute
        tool_input: parameters Claude wants to pass to the tool

    Returns:
        JSON string of tool result
    """
    if tool_name not in TOOL_MAP:
        return json.dumps({
            "error": f"Unknown tool '{tool_name}'. "
                     f"Available: {list(TOOL_MAP.keys())}"
        })

    try:
        result = TOOL_MAP[tool_name](**tool_input)
        return json.dumps(result, default=str)
    except Exception as e:
        return json.dumps({
            "error": f"Tool '{tool_name}' failed: {str(e)}"
        })


# ── The Agent Class ────────────────────────────────────────────────────────

class RestaurantAgent:
    """
    The core analytics agent for Tunday Kababi.

    Maintains conversation history across turns so the agent
    remembers context within a session.

    Usage:
        agent = RestaurantAgent(data)
        response = agent.chat("What were top selling items in April?")
        response = agent.chat("How did that compare to March?")
    """

    def __init__(
        self,
        data: dict,
        # ── Bench overrides (all optional) ────────────────────────
        model:         str  = "claude-sonnet-4-5",
        system_prompt: str  = None,          # None = use SYSTEM_PROMPT from prompts.py
        tool_definitions: list = None,       # None = use TOOL_DEFINITIONS from agent.py
    ):
        """
        Initialise the agent with loaded data.

        Args:
            data: output of load_all_data() from data_loader.py
        """
        self.client   = Anthropic()
        self.messages = []          # conversation history
        self.data     = data


        # Store overrides — bench passes these in, production uses defaults
        self._model            = model
        self._system_prompt    = system_prompt or SYSTEM_PROMPT
        self._tool_definitions = tool_definitions or TOOL_DEFINITIONS


        # Initialise tools with data
        initialise_tools(data)
        print("🤖 Restaurant Analytics Agent ready!")

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
        # ── Add user message to history ────────────────────────────────────
        self.messages.append({
            "role":    "user",
            "content": user_message
        })

        # ── Agent loop ─────────────────────────────────────────────────────
        # Keeps running until Claude returns stop_reason = "end_turn"
        # meaning it has a final answer and needs no more tools

        while True:

            # ── Call Claude ────────────────────────────────────────────────
            response = self.client.messages.create(
                model      = self._model, 
                max_tokens = 4096,
                system     = self._system_prompt,  
                tools      = self._tool_definitions,
                messages   = self.messages
            )


            # ── Check stop reason ──────────────────────────────────────────
            if response.stop_reason == "end_turn":
                # Claude has a final answer — extract and return it
                final_answer = next(
                    block.text
                    for block in response.content
                    if hasattr(block, "text")
                )

                # Add assistant response to history for next turn
                self.messages.append({
                    "role":    "assistant",
                    "content": response.content
                })

                return final_answer

            elif response.stop_reason == "tool_use":
                # Claude wants to use one or more tools
                # Add Claude's response to history first
                self.messages.append({
                    "role":    "assistant",
                    "content": response.content
                })

                # ── Process all tool calls in this response ────────────────
                # Claude can request multiple tools in one response
                tool_results = []

                for block in response.content:
                    if block.type != "tool_use":
                        continue
                    # ... execute tool, append to tool_results

                    tool_name  = block.name
                    tool_input = block.input

                    if verbose:
                        print(f"\n🔧 Tool called: {tool_name}")
                        print(f"   Input: {json.dumps(tool_input, indent=2)}")

                    # Execute the tool
                    result = execute_tool(tool_name, tool_input)

                    if verbose:
                        result_preview = result[:200] + "..." \
                            if len(result) > 200 else result
                        print(f"   Result preview: {result_preview}")

                    # Collect tool result
                    tool_results.append({
                        "type":        "tool_result",
                        "tool_use_id": block.id,
                        "content":     result
                    })
                
                # ── Safety check — never send empty content ────────────
                # If stop_reason was tool_use but somehow no tool_use blocks
                # were found, this prevents sending Claude an invalid
                # empty-content message which causes a 400 error
                if not tool_results:
                    print(f"⚠️  Warning: stop_reason was 'tool_use' but no "
                            f"tool_use blocks found in response content. "
                            f"Block types: {[b.type for b in response.content]}")
                    # Force Claude to retry by ending the loop with a fallback
                    return ("I encountered an issue processing that question. " 
                            "Could you please rephrase it?")
    
                # ── Feed all tool results back to Claude ───────────────────
                self.messages.append({
                    "role":    "user",
                    "content": tool_results
                })

                # Loop continues — Claude reads results and decides
                # whether to call more tools or give final answer

            else:
                # Unexpected stop reason
                return (
                    f"Unexpected stop reason: {response.stop_reason}. "
                    f"Please try again."
                )

    def reset(self):
        """Clear conversation history to start a fresh session."""
        self.messages = []
        print("🔄 Conversation history cleared.")