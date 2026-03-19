#!/usr/bin/env python3
"""
Agent CLI - Task 3: The System Agent

A CLI agent that uses tools (read_file, list_files, query_api) to answer questions
about the project wiki, source code, and backend API data.

Usage:
    uv run agent.py "How many items are in the database?"

Output:
    {
      "answer": "...",
      "source": "wiki/git.md",
      "tool_calls": [...]
    }
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, TypedDict

import httpx
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

# System prompt for the system agent
SYSTEM_PROMPT = """You are a system agent that helps users find information about the project.

You have access to three tools:
1. list_files - List files and directories at a given path
2. read_file - Read the contents of a file
3. query_api - Call the backend API to query data or perform operations

To answer questions:
- For wiki documentation: use list_files to explore, then read_file to find details
- For system facts (framework, ports, status codes): use read_file on source code
- For data-dependent questions (item count, scores, errors): use query_api
- For bug diagnosis: use query_api to reproduce the error, then read_file to find the bug

Rules:
- Use query_api with X-API-Key authentication (handled automatically)
- For GET requests, use method="GET"
- Include query parameters in the path (e.g., "/analytics/completion-rate?lab=lab-99")
- Call tools step by step, not all at once
- Stop when you have enough information to answer

If the question is not about this project, answer based on general knowledge.
For general knowledge questions, set source to "general-knowledge"."""


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


def tool_query_api(
    method: str,
    path: str,
    body: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> str:
    """
    Call backend API with LMS_API_KEY authentication.

    Args:
        method: HTTP method (GET, POST, PUT, DELETE)
        path: API path (e.g., "/items/", "/analytics/completion-rate")
        body: Optional JSON request body for POST/PUT
        api_key: LMS API key for authentication
        base_url: Base URL for the API

    Returns:
        JSON string with status_code and body
    """
    if not api_key:
        return json.dumps({"status_code": 0, "error": "LMS_API_KEY not configured"})

    if not base_url:
        base_url = "http://localhost:42002"

    url = f"{base_url}{path}"
    headers = {"X-API-Key": api_key}

    try:
        with httpx.Client(timeout=30.0) as client:
            if method.upper() == "GET":
                response = client.get(url, headers=headers)
            elif method.upper() == "POST":
                json_body = json.loads(body) if body else None
                response = client.post(url, headers=headers, json=json_body)
            elif method.upper() == "PUT":
                json_body = json.loads(body) if body else None
                response = client.put(url, headers=headers, json=json_body)
            elif method.upper() == "DELETE":
                response = client.delete(url, headers=headers)
            else:
                return json.dumps(
                    {"status_code": 0, "error": f"Unknown method: {method}"}
                )

            return json.dumps(
                {
                    "status_code": response.status_code,
                    "body": response.text,
                }
            )
    except httpx.TimeoutException:
        return json.dumps({"status_code": 0, "error": "API request timed out"})
    except httpx.RequestError as e:
        return json.dumps({"status_code": 0, "error": str(e)})
    except json.JSONDecodeError as e:
        return json.dumps({"status_code": 0, "error": f"Invalid JSON body: {e}"})
    except Exception as e:
        return json.dumps({"status_code": 0, "error": str(e)})


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
    {
        "type": "function",
        "function": {
            "name": "query_api",
            "description": "Call the backend API to query data or perform operations. Use for data-dependent questions (item counts, scores, errors) or to check system behavior.",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {
                        "type": "string",
                        "description": "HTTP method (GET, POST, PUT, DELETE)",
                        "enum": ["GET", "POST", "PUT", "DELETE"],
                    },
                    "path": {
                        "type": "string",
                        "description": "API path starting with / (e.g., /items/, /analytics/completion-rate?lab=lab-99)",
                    },
                    "body": {
                        "type": "string",
                        "description": "Optional JSON request body for POST/PUT requests",
                    },
                },
                "required": ["method", "path"],
            },
        },
    },
]


def execute_tool(
    name: str,
    args: dict[str, str],
    project_root: Path,
    lms_api_key: str | None = None,
    agent_api_base_url: str | None = None,
) -> str:
    """
    Execute a tool by name with the given arguments.

    Args:
        name: Tool name (read_file, list_files, query_api)
        args: Tool arguments
        project_root: Project root directory
        lms_api_key: LMS API key for query_api
        agent_api_base_url: Base URL for query_api

    Returns:
        Tool result as string
    """
    if name == "read_file":
        path = args.get("path", "")
        return tool_read_file(path, project_root)
    elif name == "list_files":
        path = args.get("path", "")
        return tool_list_files(path, project_root)
    elif name == "query_api":
        method = args.get("method", "GET")
        path = args.get("path", "")
        body = args.get("body")
        return tool_query_api(method, path, body, lms_api_key, agent_api_base_url)
    else:
        return f"Error: Unknown tool: {name}"


def extract_source_from_tool_calls(tool_calls: list[ToolCall]) -> str:
    """
    Extract source reference from tool calls.

    Returns the last read_file path from wiki/, or "general-knowledge" if none.
    """
    for tool_call in reversed(tool_calls):
        if tool_call["tool"] == "read_file":
            path = tool_call["args"].get("path", "")
            if path.startswith("wiki/"):
                return path
    return "general-knowledge"


def run_agentic_loop(
    client: OpenAI,
    model: str,
    question: str,
    project_root: Path,
    lms_api_key: str | None = None,
    agent_api_base_url: str | None = None,
) -> AgentOutput:
    """
    Run the agentic loop: LLM → tool calls → execute → LLM → ...

    Args:
        client: OpenAI client
        model: Model name
        question: User's question
        project_root: Project root directory
        lms_api_key: LMS API key for query_api
        agent_api_base_url: Base URL for query_api

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
            result = execute_tool(
                function_name,  # type: ignore[arg-type]
                function_args,
                project_root,
                lms_api_key,
                agent_api_base_url,
            )

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
    env_path_agent = project_root / ".env.agent.secret"
    env_vars_agent = load_env(str(env_path_agent))

    # Load LMS API key from .env.docker.secret
    env_path_docker = project_root / ".env.docker.secret"
    env_vars_docker = load_env(str(env_path_docker))

    api_key = env_vars_agent.get("LLM_API_KEY")
    api_base = env_vars_agent.get("LLM_API_BASE")
    model = env_vars_agent.get("LLM_MODEL", "qwen3-coder-plus")

    # Load LMS API key and agent API base URL
    lms_api_key = env_vars_docker.get("LMS_API_KEY")
    agent_api_base_url = env_vars_docker.get("AGENT_API_BASE_URL")

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
    print(f"LMS API key configured: {'yes' if lms_api_key else 'no'}", file=sys.stderr)
    print(
        f"Agent API base URL: {agent_api_base_url or 'http://localhost:42002'}",
        file=sys.stderr,
    )

    # Create OpenAI client with custom base URL
    client = OpenAI(api_key=api_key, base_url=api_base, timeout=60.0)

    try:
        # Run agentic loop
        output = run_agentic_loop(
            client,
            model,
            question,
            project_root,
            lms_api_key,
            agent_api_base_url,
        )

        # Output valid JSON to stdout
        print(json.dumps(output))

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
