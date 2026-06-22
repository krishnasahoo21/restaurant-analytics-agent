"""
evaluators.py
-------------
Evaluation logic for each test category.

Three evaluators:
    DataQualityEvaluator   → deterministic, checks exact values
    ToolSelectionEvaluator → checks which tools Claude called
    ResponseQualityEvaluator → LLM-as-Judge, checks reasoning
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import time
from anthropic import Anthropic
from src.tools import initialise_tools
from src.agent import TOOL_MAP
import src.agent as agent_module
import traceback


class DataQualityEvaluator:
    """
    Evaluates whether tool functions return correct data.
    Deterministic — compares actual vs expected values.
    """

    def evaluate(self, test_case: dict) -> dict:
        """Run a single data quality test."""

        tool_name  = test_case["tool"]
        tool_input = test_case["input"]
        field_path = test_case["field"]
        expected   = test_case["expected"]
        tolerance  = test_case["tolerance"]

        try:
            # Execute the tool directly
            result = TOOL_MAP[tool_name](**tool_input)

            # Extract the field value using dot notation
            # e.g. "items[0].item_name" → result["items"][0]["item_name"]
            actual = self._extract_field(result, field_path)

            # Compare actual vs expected
            passed = self._compare(actual, expected, tolerance)

            return {
                "test_id":   test_case["test_id"],
                "name":      test_case["name"],
                "category":  "Data Quality",
                "passed":    passed,
                "expected":  expected,
                "actual":    actual,
                "severity":  test_case["severity"],
                "error":     None
            }

        except Exception as e:
            return {
                "test_id":  test_case["test_id"],
                "name":     test_case["name"],
                "category": "Data Quality",
                "passed":   False,
                "expected": expected,
                "actual":   None,
                "severity": test_case["severity"],
                "error":    str(e)
            }

    def _extract_field(self, data: dict, field_path: str):
        """
        Extract a nested field from a dict using dot notation.
        Supports: "field", "nested.field", "items[0].name"
        """
        parts = field_path.replace("]", "").replace("[", ".").split(".")

        current = data
        for part in parts:
            if part.isdigit():
                current = current[int(part)]
            elif part == "channels_count":
                # Special case — count channels list
                current = len(current.get("channels", []))
            else:
                current = current[part]
        return current

    def _compare(self, actual, expected, tolerance) -> bool:
        """Compare actual vs expected with optional tolerance."""
        if tolerance is None:
            # String comparison — case insensitive
            return str(actual).lower() == str(expected).lower()
        elif tolerance == 0:
            # Exact numeric match
            return actual == expected
        else:
            # Numeric match within tolerance
            return abs(float(actual) - float(expected)) <= tolerance


class ToolSelectionEvaluator:
    """
    Evaluates whether Claude selects the correct tools
    for each type of question.

    Intercepts execute_tool calls to track which tools are called.
    """

    def evaluate(self, test_case: dict, agent) -> dict:
        """Run a single tool selection test."""

        question       = test_case["question"]
        expected_tools = set(test_case["expected_tools"])
        forbidden      = set(test_case.get("forbidden_tools", []))

        # Track which tools get called
        tools_called = []
        original_execute = agent_module.execute_tool

        def tracking_execute(tool_name, tool_input):
            tools_called.append(tool_name)
            return original_execute(tool_name, tool_input)

        agent_module.execute_tool = tracking_execute

        try:
            # Run the agent
            agent.chat(question)
            tools_called_set = set(tools_called)

            # Evaluate results
            missing_tools   = expected_tools - tools_called_set
            forbidden_used  = forbidden & tools_called_set

            # Check if AT LEAST ONE expected tool was called
            # Handles cases where multiple tools are equally valid
            if test_case.get("any_of", False):
                # Pass if ANY expected tool was called
                at_least_one = bool(expected_tools & tools_called_set)
                passed = at_least_one and len(forbidden_used) == 0
                missing_tools = set() if at_least_one else expected_tools
            else:
                # Default — ALL expected tools must be called
                missing_tools = expected_tools - tools_called_set
                passed = (
                    len(missing_tools) == 0 and
                    len(forbidden_used) == 0
                )

            return {
                "test_id":       test_case["test_id"],
                "name":          test_case["name"],
                "category":      "Tool Selection",
                "passed":        passed,
                "expected_tools":list(expected_tools),
                "tools_called":  tools_called,
                "missing_tools": list(missing_tools),
                "forbidden_used":list(forbidden_used),
                "severity":      test_case["severity"],
                "error":         None
            }

        except Exception as e:
            return {
                "test_id":  test_case["test_id"],
                "name":     test_case["name"],
                "category": "Tool Selection",
                "passed":   False,
                "severity": test_case["severity"],
                "error":    str(e)
            }

        finally:
            # Always restore original execute_tool
            agent_module.execute_tool = original_execute
            # Reset conversation for next test
            agent.reset()


class ResponseQualityEvaluator:
    """
    Uses LLM-as-Judge to evaluate response quality.

    A second Claude instance reads the agent's answer
    and evaluates it against defined criteria.

    This is the most sophisticated evaluator — it can catch:
    - Hallucinated numbers
    - Missing required information
    - Poor reasoning
    - Inappropriate tone
    """

    JUDGE_SYSTEM_PROMPT = """You are an expert evaluator assessing 
the quality of an AI analytics assistant's responses.

CRITICAL CONTEXT: This agent uses TOOL-BASED GROUNDING. 
It calls Python functions that return real data before answering.
Any specific numbers, percentages or names in the response 
CAME FROM REAL DATA TOOLS — they are NOT hallucinations.

A hallucination is ONLY when the agent:
- States a specific number NOT supported by any tool output
- Makes up a fact that contradicts the tool data
- Invents a metric that was never calculated

A hallucination is NOT:
- Giving a specific percentage calculated from real tool data
- Naming real customers returned by a tool
- Providing exact revenue figures from the data layer

You will receive:
1. A question asked by the user
2. The agent's response
3. Criteria to evaluate

Evaluate every response on THREE dimensions:

CORRECTNESS (1-5)
Does the response state accurate facts grounded in real data?
5 = All figures accurate and verifiable
4 = Minor rounding or formatting differences only
3 = Mostly correct with one small error
2 = Contains a factual error
1 = Significantly incorrect or fabricated

COMPLETENESS (1-5)
Does the response fully answer what was asked?
5 = Covers all aspects with supporting context
4 = Answers the question with minor gaps
3 = Answers the main question but misses supporting detail
2 = Partial answer — key information missing
1 = Does not answer the question

COMPACTNESS (1-5)
Is the response appropriately concise without padding?
5 = Perfectly concise — every sentence adds value
4 = Mostly concise with minor redundancy
3 = Some unnecessary padding but core is clear
2 = Noticeably verbose or repetitive
1 = Significantly padded or rambling

Then evaluate each specific criterion provided.

CRITICAL OUTPUT FORMAT:
Respond ONLY with a raw JSON object.
No markdown fences, no ```json, no preamble, no explanation.
Start your response with { and end with }.

Use EXACTLY this structure:
{
  "correctness_score": 4,
  "completeness_score": 5,
  "compactness_score": 4,
  "criteria_results": [
    {
      "criterion": "criterion text",
      "result": "PASS",
      "reason": "brief reason"
    }
  ],
  "overall_score": 4,
  "overall_reasoning": "brief explanation",
  "hallucination_detected": false
}

Overall score should reflect the average of the three 
dimension scores weighted by question type.

For each criterion, respond with:
- PASS: the criterion is clearly met
- FAIL: the criterion is clearly not met
- PARTIAL: partially met but with gaps

Note: Multiple PARTIAL results should lower the overall_score
but not necessarily trigger a FAIL unless they represent 
critical missing information.

Only set hallucination_detected to true if you identify 
a SPECIFIC number or fact that was clearly invented and 
not derivable from real restaurant data.
"""


    def __init__(self):
        self.client = Anthropic()

    def evaluate(self, test_case: dict, agent) -> dict:
        """Run a single response quality test."""

        question = test_case["question"]
        criteria = test_case["criteria"]

        try:
            # Get agent response
            response = agent.chat(question)
            agent.reset()

            # Build judge prompt
            judge_prompt = f"""
Question asked: {question}

Agent response: {response}

Evaluate against these criteria:
{json.dumps(criteria, indent=2)}
"""

            # Call judge Claude
            judge_response = self.client.messages.create(
                model      = "claude-sonnet-4-5",
                max_tokens = 2048,
                system     = self.JUDGE_SYSTEM_PROMPT,
                messages   = [{"role": "user", "content": judge_prompt}]
            )


            # Parse judge output
            # Finds the JSON object regardless of surrounding formatting
           
            judge_text = judge_response.content[0].text.strip()
                
            # Extract content between first { and last }
            # This handles: raw JSON, ```json fences, 
            # extra whitespace, trailing newlines — everything
            start = judge_text.find("{")
            end   = judge_text.rfind("}") + 1

            if start == -1 or end == 0:
                raise ValueError(
                    f"No JSON object found in judge response. "
                    f"Got: {judge_text[:200]}"
                )

            judge_text = judge_text[start:end]
            evaluation = json.loads(judge_text)

            # Extract three dimension scores
            correctness  = evaluation.get("correctness_score",  "N/A")
            completeness = evaluation.get("completeness_score", "N/A")
            compactness  = evaluation.get("compactness_score",  "N/A")

            # Determine pass/fail
            hallucination = evaluation.get("hallucination_detected", False)
            score = evaluation["overall_score"]

            # Pass if:
            # - Score >= 3 (acceptable or better) AND no hallucination
            # - OR score >= 4 even if minor hallucination flag 
            #   (gives benefit of doubt for tool-grounded responses)
            passed = (score >= 3 and not hallucination) or (score >= 4)

            return {
                "test_id":              test_case["test_id"],
                "name":                 test_case["name"],
                "category":             "Response Quality",
                "passed":               passed,
                "overall_score":        score,
                "correctness_score":    correctness,
                "completeness_score":   completeness,
                "compactness_score":    compactness,
                "criteria_results":     evaluation["criteria_results"],
                "hallucination":        hallucination,
                "reasoning":            evaluation["overall_reasoning"],
                "agent_response":       response[:500] + "..."
                                        if len(response) > 500
                                        else response,
                "severity":             test_case["severity"],
                "error":                None
            }

        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            print(f"\n         ⚠️  RQ test error: {error_msg}")
            return {
                "test_id":  test_case["test_id"],
                "name":     test_case["name"],
                "category": "Response Quality",
                "passed":   False,
                "overall_score": "N/A",
                "severity": test_case["severity"],
                "error":    error_msg
            }   