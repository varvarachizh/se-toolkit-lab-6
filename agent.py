#!/usr/bin/env python3
"""
Agent CLI - Task 2: The Documentation Agent

A CLI agent that uses tools (read_file, list_files) to navigate the project wiki
and answer questions with proper source references.

Usage:
    uv run agent.py "How do you resolve a merge conflict?"

Output:
    {
      "answer": "...",
      "source": "wiki/git-workflow.md#section",
      "tool_calls": [...]
    }
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, TypedDict

from openai import OpenAI


class ToolCall(TypedDict):
    """Single tool call record."""

    tool: str
    args: dict[str, str]
    result: str


class AgentOutput(TypedDict):
    """Output structure of the agent."""

    answer: str
    source: str
    tool_calls: list[ToolCall]


# Maximum tool call iterations
MAX_ITERATIONS = 10

# System prompt for the documentation agent
SYSTEM_PROMPT = """You are a documentation agent that helps users find information in the project wiki.

You have access to two tools:
1. list_files - List files and directories at a given path
2. read_file - Read the contents of a file

To answer questions:
1. First use list_files to explore the wiki directory structure
2. Then use read_file to read relevant wiki files
3. Find the specific section that answers the question
4. Include the source reference in format: wiki/filename.md#section-anchor

Rules:
- Always start by exploring the wiki directory with list_files("wiki")
- Read files one at a time with read_file
- When you find the answer, provide it with the exact source reference
- Section anchors are lowercase with hyphens (e.g., #resolving-merge-conflicts)
- Call tools step by step, not all at once
- Stop when you have enough information to answer

If the question is not about the project documentation, answer based on your general knowledge
and set source to "general-knowledge"."""


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


def validate_path(path: str, project_root: Path) -> tuple[bool, str | Path]:
    """
    Validate that a path is within the project root.

    Returns:
        Tuple of (is_valid, resolved_path_or_error_message)
    """
    # Check for path traversal attempts
    if ".." in path:
        return False, "Security error: path traversal not allowed"

    # Resolve the path
    try:
        resolved = (project_root / path).resolve()
    except Exception as e:
        return False, f"Error resolving path: {e}"

    # Check that resolved path is within project root
    project_root_resolved = project_root.resolve()
    try:
        resolved.relative_to(project_root_resolved)
        return True, resolved
    except ValueError:
        return False, "Security error: path must be within project directory"


def tool_read_file(path: str, project_root: Path) -> str:
    """
    Read a file from the project repository.

    Args:
        path: Relative path from project root
        project_root: Project root directory

    Returns:
        File contents or error message
    """
    is_valid, result = validate_path(path, project_root)
    if not is_valid:
        return str(result)

    file_path = Path(result)

    if not file_path.exists():
        return f"Error: File not found: {path}"

    if not file_path.is_file():
        return f"Error: Path is not a file: {path}"

    try:
        return file_path.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading file: {e}"


def tool_list_files(path: str, project_root: Path) -> str:
    """
    List files and directories at a given path.

    Args:
        path: Relative directory path from project root
        project_root: Project root directory

    Returns:
        Newline-separated listing or error message
    """
    is_valid, result = validate_path(path, project_root)
    if not is_valid:
        return str(result)

    dir_path = Path(result)

    if not dir_path.exists():
        return f"Error: Directory not found: {path}"

    if not dir_path.is_dir():
        return f"Error: Path is not a directory: {path}"

    try:
        entries = sorted([e.name for e in dir_path.iterdir()])
        return "\n".join(entries)
    except Exception as e:
        return f"Error listing directory: {e}"


# Tool definitions for OpenAI API
TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the project repository",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path from project root",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories at a given path",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative directory path from project root",
                    }
                },
                "required": ["path"],
            },
        },
    },
]


def execute_tool(name: str, args: dict[str, str], project_root: Path) -> str:
    """
    Execute a tool by name with the given arguments.

    Args:
        name: Tool name (read_file or list_files)
        args: Tool arguments
        project_root: Project root directory

    Returns:
        Tool result as string
    """
    if name == "read_file":
        path = args.get("path", "")
        return tool_read_file(path, project_root)
    elif name == "list_files":
        path = args.get("path", "")
        return tool_list_files(path, project_root)
    else:
        return f"Error: Unknown tool: {name}"


def extract_source_from_tool_calls(tool_calls: list[ToolCall]) -> str:
    """
    Extract source reference from tool calls.

    Returns the last read_file path, or "general-knowledge" if none.
    """
    for tool_call in reversed(tool_calls):
        if tool_call["tool"] == "read_file":
            path = tool_call["args"].get("path", "")
            if path.startswith("wiki/"):
                return f"{path}"
    return "general-knowledge"


def run_agentic_loop(
    client: OpenAI,
    model: str,
    question: str,
    project_root: Path,
) -> AgentOutput:
    """
    Run the agentic loop: LLM → tool calls → execute → LLM → ...

    Args:
        client: OpenAI client
        model: Model name
        question: User's question
        project_root: Project root directory

    Returns:
        AgentOutput with answer, source, and tool_calls
    """
    # Initialize messages with system prompt and user question
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    all_tool_calls: list[ToolCall] = []
    iteration = 0

    while iteration < MAX_ITERATIONS:
        iteration += 1
        print(f"Iteration {iteration}/{MAX_ITERATIONS}...", file=sys.stderr)

        # Send request to LLM with tools
        response = client.chat.completions.create(
            model=model,
            messages=messages,  # type: ignore[arg-type]
            tools=TOOLS,  # type: ignore[arg-type]
        )

        assistant_message = response.choices[0].message

        # Check for tool calls
        tool_calls = assistant_message.tool_calls

        if not tool_calls:
            # No tool calls - LLM provided final answer
            answer = assistant_message.content or ""
            print(f"Final answer: {answer[:100]}...", file=sys.stderr)

            # Extract source from tool calls
            source = extract_source_from_tool_calls(all_tool_calls)

            return {
                "answer": answer,
                "source": source,
                "tool_calls": all_tool_calls,
            }

        # Execute tool calls
        for tool_call in tool_calls:
            # Access tool call attributes with type hints
            function_name: str = tool_call.function.name  # type: ignore[union-attr]
            function_args: dict[str, Any] = json.loads(tool_call.function.arguments)  # type: ignore[union-attr]

            print(f"Executing tool: {function_name}({function_args})", file=sys.stderr)

            # Execute the tool
            result = execute_tool(function_name, function_args, project_root)  # type: ignore[arg-type]

            print(f"Tool result: {result[:100]}...", file=sys.stderr)

            # Record the tool call
            tool_call_record: ToolCall = {
                "tool": function_name,
                "args": function_args,
                "result": result,
            }
            all_tool_calls.append(tool_call_record)

            # Add assistant message with tool call to conversation
            messages.append(
                {
                    "role": "assistant",
                    "content": assistant_message.content,
                    "tool_calls": [
                        {
                            "id": tool_call.id,
                            "type": "function",
                            "function": {
                                "name": function_name,
                                "arguments": tool_call.function.arguments,  # type: ignore[union-attr]
                            },
                        }
                    ],
                }
            )

            # Add tool result to conversation
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )

    # Max iterations reached
    print("Max iterations reached", file=sys.stderr)
    source = extract_source_from_tool_calls(all_tool_calls)

    return {
        "answer": "Max tool call iterations reached. Partial information gathered.",
        "source": source,
        "tool_calls": all_tool_calls,
    }


def main() -> int:
    """Main entry point."""
    # Check for command-line argument
    if len(sys.argv) < 2:
        print('Usage: uv run agent.py "<question>"', file=sys.stderr)
        print("Error: No question provided", file=sys.stderr)
        return 1

    question = sys.argv[1]
    print(f"Received question: {question}", file=sys.stderr)

    # Get project root (parent of agent.py)
    project_root = Path(__file__).parent

    # Load environment variables from .env.agent.secret
    env_path = project_root / ".env.agent.secret"
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
    print(f"Project root: {project_root}", file=sys.stderr)

    # Create OpenAI client with custom base URL
    client = OpenAI(api_key=api_key, base_url=api_base, timeout=60.0)

    try:
        # Run agentic loop
        output = run_agentic_loop(client, model, question, project_root)

        # Output valid JSON to stdout
        print(json.dumps(output))

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
