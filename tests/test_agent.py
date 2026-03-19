"""
Regression tests for agent.py (Task 1)

Tests verify that the agent outputs valid JSON with the required fields.
"""

import json
import subprocess
import sys
from pathlib import Path


def test_agent_json_output():
    """Test that agent.py outputs valid JSON with 'answer' and 'tool_calls' fields."""
    # Path to agent.py in project root
    project_root = Path(__file__).parent.parent
    agent_path = project_root / "agent.py"

    # Run agent with a simple test question
    result = subprocess.run(
        [sys.executable, str(agent_path), "What does REST stand for?"],
        capture_output=True,
        text=True,
        timeout=60,
    )

    # Check exit code
    assert result.returncode == 0, f"Agent failed with stderr: {result.stderr}"

    # Parse stdout as JSON
    output = json.loads(result.stdout)

    # Verify required fields exist
    assert "answer" in output, "Missing 'answer' field in output"
    assert "tool_calls" in output, "Missing 'tool_calls' field in output"

    # Verify answer is non-empty string
    assert isinstance(output["answer"], str), "'answer' must be a string"
    assert len(output["answer"]) > 0, "'answer' must not be empty"

    # Verify tool_calls is a list
    assert isinstance(output["tool_calls"], list), "'tool_calls' must be a list"

    print(f"✓ Test passed: answer='{output['answer'][:50]}...'")
