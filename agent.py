#!/usr/bin/env python3
"""
Agent CLI - Task 1: Call an LLM from Code

A simple CLI that takes a question, sends it to an LLM via OpenAI-compatible API,
and returns a structured JSON answer.

Usage:
    uv run agent.py "What does REST stand for?"

Output:
    {"answer": "...", "tool_calls": []}
"""

import json
import os
import sys
from pathlib import Path
from typing import TypedDict

from openai import OpenAI


class AgentOutput(TypedDict):
    """Output structure of the agent."""

    answer: str
    tool_calls: list[str]


def load_env(env_path: str) -> dict[str, str]:
    """Load environment variables from a .env file."""
    env_vars: dict[str, str] = {}
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()
    return env_vars


def main() -> int:
    """Main entry point."""
    # Check for command-line argument
    if len(sys.argv) < 2:
        print('Usage: uv run agent.py "<question>"', file=sys.stderr)
        print("Error: No question provided", file=sys.stderr)
        return 1

    question = sys.argv[1]
    print(f"Received question: {question}", file=sys.stderr)

    # Load environment variables from .env.agent.secret
    env_path = Path(__file__).parent / ".env.agent.secret"
    env_vars = load_env(str(env_path))

    api_key = env_vars.get("LLM_API_KEY")
    api_base = env_vars.get("LLM_API_BASE")
    model = env_vars.get("LLM_MODEL", "qwen3-coder-plus")

    # Validate required environment variables
    if not api_key:
        print("Error: LLM_API_KEY not found in .env.agent.secret", file=sys.stderr)
        return 1

    if not api_base:
        print("Error: LLM_API_BASE not found in .env.agent.secret", file=sys.stderr)
        return 1

    print(f"Using model: {model}", file=sys.stderr)
    print(f"API base: {api_base}", file=sys.stderr)

    # Create OpenAI client with custom base URL
    client = OpenAI(api_key=api_key, base_url=api_base, timeout=60.0)

    try:
        # Send chat completion request
        print("Sending request to LLM...", file=sys.stderr)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": question,
                }
            ],
        )

        # Extract answer from response
        answer = response.choices[0].message.content or ""
        print(f"Received answer: {answer[:100]}...", file=sys.stderr)

        # Format output as JSON
        output: AgentOutput = {
            "answer": answer,
            "tool_calls": [],
        }

        # Output valid JSON to stdout
        print(json.dumps(output))

        return 0

    except Exception as e:
        print(f"Error calling LLM: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
