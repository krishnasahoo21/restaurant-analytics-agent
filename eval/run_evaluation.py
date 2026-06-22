"""
run_evaluation.py
-----------------
Main evaluation runner for the Tunday Kababi Analytics Agent.

Runs all three evaluation categories and produces a report.

Usage:
    python eval/run_evaluation.py              # run all tests
    python eval/run_evaluation.py --dq         # data quality only
    python eval/run_evaluation.py --ts         # tool selection only
    python eval/run_evaluation.py --rq         # response quality only
    python eval/run_evaluation.py --fast       # skip response quality
"""

import sys
import os

# Add project root to Python path
# This makes 'src' importable regardless of how script is run
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import sys
import time
from datetime import datetime
from pathlib import Path

from src.data_loader import load_all_data
from src.agent import RestaurantAgent
from src.tools import initialise_tools

from eval.test_cases import (
    DATA_QUALITY_TESTS,
    TOOL_SELECTION_TESTS,
    RESPONSE_QUALITY_TESTS
)
from eval.evaluators import (
    DataQualityEvaluator,
    ToolSelectionEvaluator,
    ResponseQualityEvaluator
)


def run_evaluation(
    run_dq: bool = True,
    run_ts: bool = True,
    run_rq: bool = True
):
    """
    Run the full evaluation suite.

    Args:
        run_dq: run data quality tests
        run_ts: run tool selection tests
        run_rq: run response quality tests (costs API calls)
    """

    print("\n" + "═"*60)
    print("  🧪 TUNDAY KABABI AGENT — EVALUATION SUITE")
    print("═"*60)
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("═"*60)

    # ── Setup ──────────────────────────────────────────────────────────
    print("\n📂 Loading data and initialising agent...")
    data  = load_all_data()
    initialise_tools(data)
    agent = RestaurantAgent(data)

    all_results = []
    start_time  = time.time()

    # ══════════════════════════════════════════════════════════════════
    # CATEGORY 1 — DATA QUALITY
    # ══════════════════════════════════════════════════════════════════
    if run_dq:
        print(f"\n{'─'*60}")
        print(f"  📊 DATA QUALITY TESTS ({len(DATA_QUALITY_TESTS)} tests)")
        print(f"{'─'*60}")

        evaluator = DataQualityEvaluator()

        for test in DATA_QUALITY_TESTS:
            result = evaluator.evaluate(test)
            all_results.append(result)

            status = "✅ PASS" if result["passed"] else "❌ FAIL"
            print(f"  {status}  [{result['test_id']}] {result['name']}")

            if not result["passed"] and not result["error"]:
                print(f"         Expected: {result['expected']}")
                print(f"         Actual:   {result['actual']}")
            if result["error"]:
                print(f"         Error: {result['error']}")

    # ══════════════════════════════════════════════════════════════════
    # CATEGORY 2 — TOOL SELECTION
    # ══════════════════════════════════════════════════════════════════
    if run_ts:
        print(f"\n{'─'*60}")
        print(f"  🔧 TOOL SELECTION TESTS ({len(TOOL_SELECTION_TESTS)} tests)")
        print(f"{'─'*60}")

        evaluator = ToolSelectionEvaluator()

        for test in TOOL_SELECTION_TESTS:
            print(f"  ⏳ Running: {test['name']}...")
            result = evaluator.evaluate(test, agent)
            all_results.append(result)

            status = "✅ PASS" if result["passed"] else "❌ FAIL"
            print(f"  {status}  [{result['test_id']}] {result['name']}")

            if not result["passed"] and not result.get("error"):
                if result.get("missing_tools"):
                    print(f"         Missing tools:  {result['missing_tools']}")
                if result.get("forbidden_used"):
                    print(f"         Forbidden used: {result['forbidden_used']}")
                print(f"         Called: {result.get('tools_called', [])}")

    # ══════════════════════════════════════════════════════════════════
    # CATEGORY 3 — RESPONSE QUALITY (LLM-as-Judge)
    # ══════════════════════════════════════════════════════════════════
    if run_rq:
        print(f"\n{'─'*60}")
        print(f"  🤖 RESPONSE QUALITY TESTS ({len(RESPONSE_QUALITY_TESTS)} tests)")
        print(f"  (Uses LLM-as-Judge — makes API calls)")
        print(f"{'─'*60}")

        evaluator = ResponseQualityEvaluator()

        for test in RESPONSE_QUALITY_TESTS:
            print(f"  ⏳ Evaluating: {test['name']}...")
            result = evaluator.evaluate(test, agent)
            all_results.append(result)

            status = "✅ PASS" if result["passed"] else "❌ FAIL"
            score  = result.get("overall_score", "N/A")
            c1     = result.get("correctness_score",  "N/A")
            c2     = result.get("completeness_score", "N/A")
            c3     = result.get("compactness_score",  "N/A")

            print(f"  {status}  [{result['test_id']}] {result['name']} ")
            print(f"         Correctness: {c1}/5  "
                    f"Completeness: {c2}/5  "
                    f"Compactness: {c3}/5  "
                    f"Overall: {score}/5")

            if result.get("hallucination"):
                print(f"         ⚠️  HALLUCINATION DETECTED")
            if not result["passed"] and result.get("reasoning"):
                print(f"         Reason: {result['reasoning'][:100]}...")

    # ══════════════════════════════════════════════════════════════════
    # SUMMARY REPORT
    # ══════════════════════════════════════════════════════════════════
    elapsed = round(time.time() - start_time, 1)

    total    = len(all_results)
    passed   = sum(1 for r in all_results if r["passed"])
    failed   = total - passed
    pass_pct = round(passed / total * 100, 1) if total > 0 else 0

    # Severity breakdown
    critical_fails = [
        r for r in all_results
        if not r["passed"] and r.get("severity") == "critical"
    ]
    high_fails = [
        r for r in all_results
        if not r["passed"] and r.get("severity") == "high"
    ]

    # Hallucinations
    hallucinations = [
        r for r in all_results
        if r.get("hallucination")
    ]

    rq_results = [
        r for r in all_results
        if r.get("category") == "Response Quality"
        and r.get("overall_score") != "N/A"
    ]

    def avg_score(results, field):
        scores = [
            r.get(field) for r in results
            if isinstance(r.get(field), (int, float))
        ]
        return round(sum(scores) / len(scores), 2) if scores else "N/A"

    # Overall health
    if len(critical_fails) == 0 and pass_pct >= 80:
        health = "🟢 HEALTHY"
    elif len(critical_fails) <= 1 and pass_pct >= 60:
        health = "🟡 NEEDS ATTENTION"
    else:
        health = "🔴 FAILING"

    report = {
        "timestamp":   datetime.now().isoformat(),
        "summary": {
            "total":            total,
            "passed":           passed,
            "failed":           failed,
            "pass_rate_pct":    pass_pct,
            "critical_failures":len(critical_fails),
            "hallucinations":   len(hallucinations),
            "health":           health,
            "elapsed_seconds":  elapsed,
            "response_quality": {
                "tests_run":           len(rq_results),
                "avg_correctness":     avg_score(rq_results, "correctness_score"),
                "avg_completeness":    avg_score(rq_results, "completeness_score"),
                "avg_compactness":     avg_score(rq_results, "compactness_score"),
                "avg_overall":         avg_score(rq_results, "overall_score"),
            }
        },
        "results": all_results
    }

    print(f"\n{'═'*60}")
    print(f"  📋 EVALUATION SUMMARY")
    print(f"{'═'*60}")
    print(f"  Total tests:      {total}")
    print(f"  Passed:           {passed} ({pass_pct}%)")
    print(f"  Failed:           {failed}")
    print(f"  Time taken:       {elapsed}s")
    print(f"{'─'*60}")
    print(f"  Critical failures: {len(critical_fails)}")
    print(f"  High failures:     {len(high_fails)}")
    print(f"  Hallucinations:    {len(hallucinations)}")
    print(f"{'─'*60}")
    print(f"  Agent Health:      {health}")

    rq_summary = report["summary"].get("response_quality", {})
    if rq_summary and rq_summary.get("tests_run", 0) > 0:
        print(f"\n  📊 Response Quality Dimensions")
        print(f"{'─'*60}")
        print(f"  Correctness:   {rq_summary['avg_correctness']}/5")
        print(f"  Completeness:  {rq_summary['avg_completeness']}/5")
        print(f"  Compactness:   {rq_summary['avg_compactness']}/5")
        print(f"  Overall:       {rq_summary['avg_overall']}/5")

    # ── Save report ────────────────────────────────────────────────────
    report_path = Path("eval/reports") / \
        f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\n  📄 Full report saved: {report_path}")

    return report


# ── CLI Entry Point ────────────────────────────────────────────────────────
if __name__ == "__main__":
    args = sys.argv[1:]

    run_dq = "--dq" in args or (not args) or "--fast" in args
    run_ts = "--ts" in args or (not args) or "--fast" in args
    run_rq = "--rq" in args or ("--fast" not in args and not args)

    if "--fast" in args:
        print("  ⚡ Fast mode — skipping response quality tests")
        run_rq = False

    run_evaluation(run_dq=run_dq, run_ts=run_ts, run_rq=run_rq)