"""
Week 6: Access Control, Rate Limiting & Cost Enforcement Starter Template

Implement three guardrails:
1. AccessController - role-based document/field access control
2. RateLimiter - limit queries per minute per user
3. CostEnforcer - enforce budget limits per role
"""

import json
import logging
import time
import re
from typing import Dict, Any, List
from datetime import datetime
from time import time


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# TASK 1: Implement AccessController
# ============================================================================

class AccessController:
    """Enforce role-based access control."""

    def __init__(self, access_policy_path: str):
        with open(access_policy_path, "r") as f:
            self.policy = json.load(f)

        self.audit_log = []

    def can_view_document(self, role: str, document: Dict[str, Any]) -> bool:
        sensitivity = document.get("sensitivity", "Public")

        document_access = self.policy.get("document_access", {})

        allowed_roles = document_access.get(sensitivity, [])

        return role in allowed_roles

    def can_view_field(self, role: str, field_name: str) -> bool:
        sensitive_fields = self.policy.get("sensitive_fields", {})

        if field_name not in sensitive_fields:
            return True

        allowed_roles = sensitive_fields[field_name].get("visibility", [])

        return role in allowed_roles

    def redact_response(self, role: str, response: str) -> str:
        redacted = response
        sensitive_fields = self.policy.get("sensitive_fields", {})

        for field_name in sensitive_fields:
            if not self.can_view_field(role, field_name):
                pattern = rf'("{field_name}"\s*:\s*)("[^"]*"|\d+\.?\d*|true|false|null)'
                redacted = re.sub(
                    pattern,
                    rf'\1"[REDACTED]"',
                    redacted,
                    flags=re.IGNORECASE,
                )

        return redacted

    def log_access(self, role: str, resource: str, allowed: bool, field: str = None):
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "role": role,
            "resource": resource,
            "allowed": allowed,
        }

        if field is not None:
            entry["field"] = field

        self.audit_log.append(entry)

    def filter_documents(
        self, role: str, documents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:

        visible_documents = []

        for doc in documents:
            resource = doc.get("id", doc.get("title", "unknown_document"))
            allowed = self.can_view_document(role, doc)

            self.log_access(role, resource, allowed)

            if allowed:
                visible_documents.append(doc)

        return visible_documents

    def get_audit_log(self) -> List[Dict[str, Any]]:
        return self.audit_log


# ============================================================================
# TASK 2: Implement RateLimiter
# ============================================================================

class RateLimiter:
    """Rate limit queries per user per minute."""

    def __init__(self, max_queries_per_minute: int = 30):
        self.max_queries_per_minute = max_queries_per_minute
        self.user_query_times = {}  # {user_id: [timestamps...]}

    def is_allowed(self, user_id: str) -> bool:
        """Check if user can make another query."""

        current_time = __import__("time").time()

        if user_id not in self.user_query_times:
            self.user_query_times[user_id] = []

        # Keep only queries from the last 60 seconds
        self.user_query_times[user_id] = [
            t
            for t in self.user_query_times[user_id]
            if current_time - t < 60
        ]

        # Check rate limit
        if len(self.user_query_times[user_id]) < self.max_queries_per_minute:
            self.user_query_times[user_id].append(current_time)
            return True

        return False

    def get_remaining_queries(self, user_id: str) -> int:
        """Get remaining queries for user in current minute."""

        current_time = __import__("time").time()

        if user_id not in self.user_query_times:
            return self.max_queries_per_minute

        # Keep only recent queries
        self.user_query_times[user_id] = [
            t
            for t in self.user_query_times[user_id]
            if current_time - t < 60
        ]

        remaining = (
            self.max_queries_per_minute
            - len(self.user_query_times[user_id])
        )

        return max(0, remaining)


# ============================================================================
# TASK 3: Implement CostEnforcer
# ============================================================================


class CostEnforcer:
    """Enforce cost limits per user/role."""

    def __init__(self, policy_path: str = None):
        self.role_budgets = {
            "engineer": 100.0,
            "manager": 500.0,
            "hr": 200.0,
            "finance": 500.0,
            "executive": 1000.0,
        }

        self.user_spending = {}  # {user_id: {"role": "engineer", "total": 50.0}}

    def add_cost(self, user_id: str, role: str, cost: float):
        """Record cost for user."""

        if user_id not in self.user_spending:
            self.user_spending[user_id] = {
                "role": role,
                "total": 0.0,
            }

        self.user_spending[user_id]["total"] += cost

    def can_afford_query(self, user_id: str, estimated_cost: float) -> bool:
        """Check if user has budget remaining."""

        if user_id not in self.user_spending:
            role = "engineer"
            budget = self.role_budgets.get(role, 0.0)
            return estimated_cost <= budget

        remaining = self.get_budget_remaining(user_id)
        return estimated_cost <= remaining

    def get_budget_remaining(self, user_id: str) -> float:
        """Get remaining budget for user."""

        if user_id not in self.user_spending:
            return 0.0

        role = self.user_spending[user_id]["role"]
        total_spent = self.user_spending[user_id]["total"]

        budget = self.role_budgets.get(role, 0.0)
        remaining = budget - total_spent

        return max(0.0, remaining)


# ============================================================================
# TASK 4: Integrate with Week 5 Agent
# ============================================================================

# Once you have implemented the three classes above, open your copied
# app_starter.py and update the Agent class to use them:
#
# 1. In Agent.__init__, add:
#       self.access_controller = AccessController("data/access_control.json")
#       self.rate_limiter = RateLimiter(max_queries_per_minute=30)
#       self.cost_enforcer = CostEnforcer()
#
# 2. Update Agent.query() to accept user_id and user_role parameters:
#       def query(self, user_query: str, user_id: str, user_role: str = "engineer")
#
# 3. At the start of query(), add guardrail checks:
#       if not self.rate_limiter.is_allowed(user_id):
#           return {"error": "Rate limit exceeded"}
#       if not self.cost_enforcer.can_afford_query(user_id, estimated_cost=0.01):
#           return {"error": "Budget exceeded"}
#
# 4. After getting the LLM answer, redact sensitive fields:
#       answer = self.access_controller.redact_response(user_role, answer)
#
# 5. After each query, track actual cost:
#       self.cost_enforcer.add_cost(user_id, user_role, actual_cost)


# ============================================================================
# TASK 5: Test Your Implementation
# ============================================================================

# A basic test suite is provided below to help you verify your implementation.
# Run it with: python3 access_control_starter.py
# You are free to modify or extend these tests as you see fit.

if __name__ == "__main__":
    """Quick test of access control functionality."""

    # Test AccessController
    print("Testing AccessController...")
    controller = AccessController("data/access_control.json")

    assert not controller.can_view_field(
        "engineer", "salary"
    ), "Engineer should not see salary"
    assert controller.can_view_field("hr", "salary"), "HR should see salary"
    assert controller.can_view_field("manager", "salary"), "Manager should see salary"
    assert not controller.can_view_field(
        "engineer", "ssn"
    ), "Engineer should not see SSN"
    print("  can_view_field: PASSED")

    docs = [
        {"id": "doc1", "sensitivity": "Public", "content": "Mission statement"},
        {"id": "doc2", "sensitivity": "Confidential", "content": "Salary ranges"},
    ]
    visible = controller.filter_documents("engineer", docs)
    assert (
        len(visible) == 1 and visible[0]["id"] == "doc1"
    ), "Engineer should only see Public doc"
    print("  filter_documents: PASSED")

    # Test RateLimiter
    print("\nTesting RateLimiter...")
    limiter = RateLimiter(max_queries_per_minute=3)
    assert limiter.is_allowed("user1"), "First query should be allowed"
    assert limiter.is_allowed("user1"), "Second query should be allowed"
    assert limiter.is_allowed("user1"), "Third query should be allowed"
    assert not limiter.is_allowed("user1"), "Fourth query should be blocked"
    print("  is_allowed: PASSED")

    # Test CostEnforcer
    print("\nTesting CostEnforcer...")
    enforcer = CostEnforcer()
    assert enforcer.can_afford_query(
        "user1", 50.0
    ), "Should afford $50 within $100 budget"
    enforcer.add_cost("user1", "engineer", 50.0)
    assert enforcer.can_afford_query(
        "user1", 49.0
    ), "Should afford $49 with $50 remaining"
    assert not enforcer.can_afford_query(
        "user1", 51.0
    ), "Should not afford $51 with $50 remaining"
    print("  can_afford_query: PASSED")

    print("\nAll tests passed!")
