"""
Regression tests for agent.py (Task 1 & Task 2)

Tests verify that the agent outputs valid JSON with the required fields
and uses tools correctly.
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
    assert "source" in output, "Missing 'source' field in output"

    # Verify answer is non-empty string
    assert isinstance(output["answer"], str), "'answer' must be a string"
    assert len(output["answer"]) > 0, "'answer' must not be empty"

    # Verify tool_calls is a list
    assert isinstance(output["tool_calls"], list), "'tool_calls' must be a list"

    # Verify source is a string
    assert isinstance(output["source"], str), "'source' must be a string"

    print(f"✓ Test passed: answer='{output['answer'][:50]}...'")


def test_agent_merge_conflict_question():
    """Test that agent uses read_file for merge conflict question."""
    project_root = Path(__file__).parent.parent
    agent_path = project_root / "agent.py"

    # Run agent with merge conflict question
    result = subprocess.run(
        [sys.executable, str(agent_path), "How do you resolve a merge conflict?"],
        capture_output=True,
        text=True,
        timeout=120,
    )

    # Check exit code
    assert result.returncode == 0, f"Agent failed with stderr: {result.stderr}"

    # Parse stdout as JSON
    output = json.loads(result.stdout)

    # Verify required fields
    assert "answer" in output, "Missing 'answer' field"
    assert "source" in output, "Missing 'source' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"

    # Verify read_file was used
    tool_names = [tc.get("tool") for tc in output["tool_calls"]]
    assert "read_file" in tool_names, "Expected read_file to be called"

    # Verify source contains wiki/git.md or similar
    source = output["source"]
    assert source.startswith("wiki/"), (
        f"Source should start with 'wiki/', got: {source}"
    )
    assert ".md" in source, f"Source should contain .md extension, got: {source}"

    print(f"✓ Test passed: source='{source}', tool_calls={len(output['tool_calls'])}")


def test_agent_wiki_listing_question():
    """Test that agent uses list_files for wiki listing question."""
    project_root = Path(__file__).parent.parent
    agent_path = project_root / "agent.py"

    # Run agent with wiki listing question
    result = subprocess.run(
        [sys.executable, str(agent_path), "What files are in the wiki?"],
        capture_output=True,
        text=True,
        timeout=120,
    )

    # Check exit code
    assert result.returncode == 0, f"Agent failed with stderr: {result.stderr}"

    # Parse stdout as JSON
    output = json.loads(result.stdout)

    # Verify required fields
    assert "answer" in output, "Missing 'answer' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"

    # Verify list_files was used
    tool_names = [tc.get("tool") for tc in output["tool_calls"]]
    assert "list_files" in tool_names, "Expected list_files to be called"

    # Verify tool_calls has results
    assert len(output["tool_calls"]) > 0, "Expected at least one tool call"

    print(f"✓ Test passed: tool_calls={len(output['tool_calls'])}")
