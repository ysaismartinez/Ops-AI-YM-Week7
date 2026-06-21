"""
Week 7: Cost Optimization & Feedback Loop Starter Template

Implement three systems:
1. CostAnalyzer - analyze and track query costs
2. OptimizationStrategy - optimize costs through caching, model selection, etc.
3. FeedbackLoop - collect and validate user corrections
"""

import json
import logging
import statistics
from typing import Dict, List, Any
from datetime import datetime, UTC

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CostAnalyzer:
    """Analyze and track query costs by component."""

    def __init__(self):
        self.query_history = []

    def record_query(self, query: Dict[str, Any]):
        retrieval_cost = float(query.get("retrieval_cost", 0.0))
        llm_cost = float(query.get("llm_cost", 0.0))
        tool_cost = float(query.get("tool_cost", 0.0))
        error_cost = float(query.get("error_cost", 0.0))

        record = {
            "query_text": query.get("query_text", ""),
            "retrieval_cost": retrieval_cost,
            "llm_cost": llm_cost,
            "tool_cost": tool_cost,
            "error_cost": error_cost,
            "total_cost": retrieval_cost + llm_cost + tool_cost + error_cost,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        self.query_history.append(record)

    def get_cost_breakdown(self) -> Dict[str, Any]:
        retrieval_total = sum(q["retrieval_cost"] for q in self.query_history)
        llm_total = sum(q["llm_cost"] for q in self.query_history)
        tool_total = sum(q["tool_cost"] for q in self.query_history)
        error_total = sum(q["error_cost"] for q in self.query_history)
        total_daily = sum(q["total_cost"] for q in self.query_history)

        return {
            "retrieval_total": retrieval_total,
            "llm_total": llm_total,
            "tool_total": tool_total,
            "error_total": error_total,
            "total_daily": total_daily,
            "query_count": len(self.query_history),
        }

    def identify_cost_spikes(self) -> List[Dict]:
        if len(self.query_history) < 2:
            return []

        costs = [q["total_cost"] for q in self.query_history]
        mean_cost = statistics.mean(costs)
        stdev_cost = statistics.stdev(costs)
        threshold = mean_cost + (2 * stdev_cost)

        spikes = []
        for q in self.query_history:
            if q["total_cost"] > threshold:
                spikes.append({
                    "query_text": q["query_text"],
                    "total_cost": q["total_cost"],
                    "threshold": threshold,
                    "timestamp": q["timestamp"],
                })

        return spikes


class OptimizationStrategy:
    """Optimize agent costs through multiple strategies."""

    def __init__(self):
        self.cache = {}
        self.strategies_applied = []

    def apply_caching(self, query: str, response: str) -> tuple:
        normalized_query = query.strip().lower()

        if normalized_query in self.cache:
            self.strategies_applied.append("cache_hit")
            return True, self.cache[normalized_query]

        self.cache[normalized_query] = response
        self.strategies_applied.append("cache_store")
        return False, response

    def optimize_retrieval_count(self, num_docs: int) -> int:
        optimized_count = min(3, max(1, num_docs))
        self.strategies_applied.append("retrieval_optimization")
        return optimized_count

    def select_model_by_complexity(self, query: str) -> str:
        query_lower = query.lower()

        complex_terms = [
            "analyze", "compare", "design", "evaluate", "explain in detail",
            "strategy", "architecture", "tradeoff", "trade-off", "risk",
            "implementation", "multi-step", "complex"
        ]

        if any(term in query_lower for term in complex_terms) or len(query.split()) > 20:
            self.strategies_applied.append("pro_model_selected")
            return "gemini-2.5-pro"

        self.strategies_applied.append("flash_model_selected")
        return "gemini-1.5-flash"

    def enable_response_compression(self, response: str) -> str:
        sentences = [s.strip() for s in response.split(".") if s.strip()]

        if len(sentences) <= 3:
            return response

        compressed = ". ".join(sentences[:3]) + "."
        self.strategies_applied.append("response_compression")
        return compressed

    def get_optimization_impact(self) -> Dict[str, Any]:
        breakdown = {
            "cache_hit": 30.0,
            "retrieval_optimization": 20.0,
            "flash_model_selected": 25.0,
            "response_compression": 10.0,
        }

        applied_savings = [
            breakdown[strategy]
            for strategy in self.strategies_applied
            if strategy in breakdown
        ]

        total_savings_pct = min(sum(applied_savings), 75.0)

        return {
            "total_savings_pct": total_savings_pct,
            "strategies_applied": self.strategies_applied,
            "breakdown": {
                strategy: breakdown[strategy]
                for strategy in set(self.strategies_applied)
                if strategy in breakdown
            },
        }


class FeedbackLoop:
    """Collect and validate user corrections for continuous improvement."""

    def __init__(self):
        self.corrections = []
        self.authority = {
            "engineer": 1,
            "hr": 2,
            "finance": 2,
            "manager": 3,
            "executive": 4,
        }

    def submit_correction(
        self,
        original_query: str,
        original_answer: str,
        corrected_answer: str,
        user_role: str,
    ) -> Dict[str, Any]:

        role_level = self.authority.get(user_role.lower(), 0)

        correction = {
            "original_query": original_query,
            "original_answer": original_answer,
            "corrected_answer": corrected_answer,
            "user_role": user_role.lower(),
            "timestamp": datetime.now(UTC).isoformat(),
            "validated": False,
        }

        if role_level < 3:
            return {
                "accepted": False,
                "reason": "Correction rejected: user role does not have sufficient authority."
            }

        if len(corrected_answer.strip()) <= len(original_answer.strip()):
            return {
                "accepted": False,
                "reason": "Correction rejected: corrected answer must be more detailed than original answer."
            }

        self.corrections.append(correction)
        index = len(self.corrections) - 1
        correction["validated"] = self.validate_correction(index)

        return {
            "accepted": True,
            "reason": "Correction accepted and stored for review."
        }

    def validate_correction(self, index: int) -> bool:
        if index < 0 or index >= len(self.corrections):
            return False

        correction = self.corrections[index]
        role_level = self.authority.get(correction["user_role"], 0)

        if role_level < 3:
            return False

        if len(correction["corrected_answer"].strip()) <= len(correction["original_answer"].strip()):
            return False

        if len(correction["corrected_answer"].split()) < 5:
            return False

        return True

    def get_feedback_metrics(self) -> Dict[str, Any]:
        total = len(self.corrections)

        if total == 0:
            return {
                "total_corrections": 0,
                "validation_rate": 0.0,
                "avg_correction_length": 0.0,
                "top_error_patterns": [],
            }

        valid_count = sum(1 for c in self.corrections if c.get("validated", False))
        avg_length = sum(len(c["corrected_answer"]) for c in self.corrections) / total

        patterns = {}
        for c in self.corrections:
            original = c["original_answer"].lower()

            if "no specific policy" in original or "unknown" in original:
                pattern = "missing_policy_detail"
            elif "incorrect" in original or "wrong" in original:
                pattern = "incorrect_answer"
            elif len(original) < 50:
                pattern = "incomplete_answer"
            else:
                pattern = "general_correction"

            patterns[pattern] = patterns.get(pattern, 0) + 1

        top_error_patterns = sorted(
            patterns.items(),
            key=lambda item: item[1],
            reverse=True
        )

        return {
            "total_corrections": total,
            "validation_rate": valid_count / total,
            "avg_correction_length": avg_length,
            "top_error_patterns": top_error_patterns,
        }


if __name__ == "__main__":
    print("Testing CostAnalyzer...")
    analyzer = CostAnalyzer()

    analyzer.record_query({
        "query_text": "What is the travel policy?",
        "retrieval_cost": 0.02,
        "llm_cost": 0.08,
        "tool_cost": 0.01,
        "error_cost": 0.00,
    })

    analyzer.record_query({
        "query_text": "Analyze all travel expenses by department.",
        "retrieval_cost": 0.10,
        "llm_cost": 0.35,
        "tool_cost": 0.05,
        "error_cost": 0.02,
    })

    analyzer.record_query({
        "query_text": "Run a complex multi-agent analysis over all company documents.",
        "retrieval_cost": 2.50,
        "llm_cost": 8.00,
        "tool_cost": 1.25,
        "error_cost": 0.75,
    })

    print(json.dumps(analyzer.get_cost_breakdown(), indent=2))
    print(json.dumps(analyzer.identify_cost_spikes(), indent=2))

    print("\nTesting OptimizationStrategy...")
    optimizer = OptimizationStrategy()

    print(optimizer.apply_caching("What is the travel policy?", "Employees may book economy flights."))
    print(optimizer.apply_caching("What is the travel policy?", "This should return cached response."))
    print(optimizer.optimize_retrieval_count(15))
    print(optimizer.select_model_by_complexity("What is the PTO policy?"))
    print(optimizer.select_model_by_complexity("Analyze and compare the cost tradeoffs of three model architectures."))
    print(optimizer.enable_response_compression(
        "Sentence one. Sentence two. Sentence three. Sentence four. Sentence five."
    ))
    print(json.dumps(optimizer.get_optimization_impact(), indent=2))

    print("\nTesting FeedbackLoop...")
    feedback = FeedbackLoop()

    print(feedback.submit_correction(
        original_query="What is the travel policy for flights over 8 hours?",
        original_answer="There is no specific policy for 8+ hour flights.",
        corrected_answer="Employees can book business class for flights over 8 hours with manager approval.",
        user_role="manager",
    ))

    print(feedback.submit_correction(
        original_query="What is the travel policy?",
        original_answer="Employees may book economy.",
        corrected_answer="Business class is always allowed.",
        user_role="engineer",
    ))

    print(json.dumps(feedback.get_feedback_metrics(), indent=2))