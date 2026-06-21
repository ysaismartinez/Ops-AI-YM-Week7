"""
Week 5: Agent Architecture Starter Template

Build an AI agent that answers TechCorp questions using:
- Gemini 2.5 Pro LLM (free tier via Google AI API)
- SQLite database queries
- Policy document retrieval

Complete the TODO sections marked below.
"""

import json
import sqlite3
from typing import Dict, Any
import google.genai as genai
import logging
import os
from access_control_starter import (
    AccessController,
    RateLimiter,
    CostEnforcer,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")


# TASK 1: Implement the Tool base class


class Tool:
    """Base class for tools the agent can call."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    def execute(self, **kwargs) -> str:
        """Execute the tool.

        TODO: This is implemented by subclasses.
        Each subclass should override this method.
        """
        raise NotImplementedError


# TASK 2: Implement EmployeeLookupTool


class EmployeeLookupTool(Tool):
    """Look up employee information from SQLite database."""

    def __init__(self, db_path: str):
        super().__init__("employee_lookup", "Find employee information by name or ID")
        self.db_path = db_path

    def execute(self, employee_name: str = None, employee_id: str = None) -> str:
        """Look up employee by name or ID."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if employee_id:
                cursor.execute(
                    "SELECT * FROM employees WHERE id = ?",
                    (employee_id,)
                )
            elif employee_name:
                cursor.execute(
                    "SELECT * FROM employees WHERE name LIKE ?",
                    (f"%{employee_name}%",)
                )
            else:
                return "Error: Please provide employee_name or employee_id"

            rows = cursor.fetchall()
            conn.close()

            if not rows:
                return "Employee not found"

            results = [dict(row) for row in rows]
            return json.dumps(results, indent=2)

        except Exception as e:
            logger.error(f"Employee lookup error: {e}")
            return f"Error: {str(e)}"


# TASK 3: Implement PolicySearchTool


class PolicySearchTool(Tool):
    """Search policy documents by keyword."""

    def __init__(self):
        super().__init__("policy_search", "Search policy documents by keyword or topic")

        with open("data/documents.json", "r") as f:
            self.documents = json.load(f)

    def execute(self, query: str, limit: int = 5) -> str:
        """Search policies by keyword."""
        try:
            query_lower = query.lower()

            matches = [
                doc for doc in self.documents
                if query_lower in doc.get("content", "").lower()
                or query_lower in doc.get("title", "").lower()
            ]

            if not matches:
                return "No matching policy documents found"

            results = []
            for doc in matches[:limit]:
                title = doc.get("title", "Untitled")
                content = doc.get("content", "")
                snippet = content[:500]

                results.append(
                    f"Title: {title}\n"
                    f"Snippet: {snippet}"
                )

            return "\n\n".join(results)

        except Exception as e:
            logger.error(f"Policy search error: {e}")
            return f"Error: {str(e)}"


# TASK 4: Implement ExpenseQueryTool


class ExpenseQueryTool(Tool):
    """Query expense policies and approval limits."""

    def __init__(self):
        super().__init__("expense_query", "Query expense approval limits by role")

        with open("data/policies.json", "r") as f:
            self.policies = json.load(f)

    def execute(self, role: str) -> str:
        """Query expense approval limit for a given role."""
        try:
            approval_limits = self.policies["expense"]["approval_limits"]

            if role not in approval_limits:
                return f"Role not found: {role}"

            amount = approval_limits[role]
            return f"Approval limit for {role}: ${amount}"

        except Exception as e:
            logger.error(f"Expense query error: {e}")
            return f"Error: {str(e)}"


# TASK 5: Implement the Agent class

class Agent:
    """AI agent that answers questions using Gemini LLM + tools."""

    def __init__(self, db_path: str, api_key: str = None):
        self.db_path = db_path
        self.api_key = api_key or GOOGLE_API_KEY

        if not self.api_key:
            raise ValueError(
                "GOOGLE_API_KEY not set. Get free key at: "
                "https://aistudio.google.com/app/apikey"
            )

        self.client = genai.Client(api_key=self.api_key)

        self.tools = {
            "employee_lookup": EmployeeLookupTool(db_path),
            "policy_search": PolicySearchTool(),
            "expense_query": ExpenseQueryTool(),
        }

        # Week 6 Guardrails
        self.access_controller = AccessController("data/access_control.json")
        self.rate_limiter = RateLimiter(max_queries_per_minute=30)
        self.cost_enforcer = CostEnforcer()

        self.token_count = 0
        self.total_cost = 0.0
        self.queries_run = 0

    def _build_system_prompt(self, user_role: str) -> str:
        tool_descriptions = "\n".join(
            [f"- {name}: {tool.description}" for name, tool in self.tools.items()]
        )

        return f"""
You are a TechCorp assistant. Answer employee questions using the available tools.

User role: {user_role}

Available tools:
{tool_descriptions}

Use these tools when needed:
- employee_lookup: use for questions about employees by name or ID.
- policy_search: use for questions about company policies, travel, PTO, benefits, or security.
- expense_query: use for questions about expense approval limits by role.

When you need a tool, respond exactly in this format:
TOOL: <tool_name>
ARGS: <argument_name>=<argument_value>

Examples:
TOOL: employee_lookup
ARGS: employee_name=Sarah

TOOL: expense_query
ARGS: role=manager

TOOL: policy_search
ARGS: query=travel policy

If no tool is needed, answer directly.
"""

    def _parse_tool_call(self, llm_text: str):
        tool_name = None
        args = {}

        lines = llm_text.strip().splitlines()

        for line in lines:
            line = line.strip()

            if line.startswith("TOOL:"):
                tool_name = line.replace("TOOL:", "").strip()

            elif line.startswith("ARGS:"):
                arg_text = line.replace("ARGS:", "").strip()

                if "=" in arg_text:
                    key, value = arg_text.split("=", 1)
                    args[key.strip()] = value.strip()

        return tool_name, args

    def _estimate_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)

    def query(
        self,
        user_query: str,
        user_id: str = "default_user",
        user_role: str = "engineer",
    ) -> Dict[str, Any]:

        logger.info(f"Processing query: {user_query}")

        # ==================================================
        # WEEK 6 GUARDRAILS
        # ==================================================

        estimated_cost = 0.01

        if not self.rate_limiter.is_allowed(user_id):
            return {"error": "Rate limit exceeded"}

        if user_id not in self.cost_enforcer.user_spending:
            self.cost_enforcer.user_spending[user_id] = {
                "role": user_role,
                "total": 0.0,
            }

        if not self.cost_enforcer.can_afford_query(
            user_id, estimated_cost
        ):
            return {"error": "Budget exceeded"}

        # ==================================================
        # ORIGINAL WEEK 5 LOGIC
        # ==================================================

        system_prompt = self._build_system_prompt(user_role)

        first_prompt = f"""
{system_prompt}

User question:
{user_query}
"""

        first_response = self.client.models.generate_content(
            model="models/gemini-2.5-flash",
            contents=first_prompt
        )

        first_text = first_response.text or ""

        input_tokens_1 = self._estimate_tokens(first_prompt)
        output_tokens_1 = self._estimate_tokens(first_text)

        tool_name, tool_args = self._parse_tool_call(first_text)

        if tool_name in self.tools:
            tool_result = self.tools[tool_name].execute(**tool_args)

            final_prompt = f"""
You are a TechCorp assistant.

User question:
{user_query}

Tool used:
{tool_name}

Tool result:
{tool_result}

Write a clear final answer for the user.
"""

            final_response = self.client.models.generate_content(
                model="models/gemini-2.5-flash",
                contents=final_prompt
            )

            answer = final_response.text or ""

            input_tokens_2 = self._estimate_tokens(final_prompt)
            output_tokens_2 = self._estimate_tokens(answer)

        else:
            answer = first_text
            input_tokens_2 = 0
            output_tokens_2 = 0

        total_input_tokens = input_tokens_1 + input_tokens_2
        total_output_tokens = output_tokens_1 + output_tokens_2
        total_tokens = total_input_tokens + total_output_tokens

        cost = self._estimate_query_cost(
            total_input_tokens,
            total_output_tokens
        )

        self.token_count += total_tokens
        self.total_cost += cost
        self.queries_run += 1

        # ==================================================
        # WEEK 6 POST-PROCESSING
        # ==================================================

        answer = self.access_controller.redact_response(
            user_role,
            answer
        )

        self.cost_enforcer.add_cost(
            user_id,
            user_role,
            cost
        )

        return {
            "answer": answer,
            "tokens_used": total_tokens,
            "cost": cost,
            "role": user_role,
            "budget_remaining": self.cost_enforcer.get_budget_remaining(user_id),
            "remaining_queries": self.rate_limiter.get_remaining_queries(user_id),
        }

    def _estimate_query_cost(
        self,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        input_cost = (input_tokens / 1_000_000) * 0.075
        output_cost = (output_tokens / 1_000_000) * 0.3
        return input_cost + output_cost

    def get_metrics(self) -> Dict[str, Any]:
        avg_cost = (
            self.total_cost / self.queries_run
            if self.queries_run > 0
            else 0.0
        )

        return {
            "total_queries": self.queries_run,
            "total_tokens": self.token_count,
            "total_cost": self.total_cost,
            "avg_cost_per_query": avg_cost,
        }

# TASK 6: Test your implementation

if __name__ == "__main__":
    """Quick test of agent functionality."""
    import sys

    try:
        # Initialize agent
        agent = Agent("data/techcorp.db")
        print("Agent initialized successfully")

        # Test a query
        print("\nTesting query: 'What is the travel policy?'")
        result = agent.query("What is the travel policy?")
        print(f"Answer: {result['answer']}")
        print(f"Tokens: {result['tokens_used']}")
        print(f"Cost: ${result['cost']:.6f}")

        # Check metrics
        metrics = agent.get_metrics()
        print(f"\nMetrics: {metrics}")

    except Exception as e:
        print(f"Error: {e}")
        logger.exception("Error during test")
        sys.exit(1)
