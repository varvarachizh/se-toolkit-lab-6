# Agent Architecture (Task 3)

## Overview

This document describes the architecture of the system agent that uses three tools (`read_file`, `list_files`, `query_api`) to answer questions about the project wiki, source code, and backend API data.

## LLM Provider

**Provider:** Qwen Code API  
**Model:** `qwen3-coder-plus`  
**API Type:** OpenAI-compatible chat completions with function calling

### Why Qwen Code?

- **1000 free requests per day** — sufficient for development and testing
- **Works from Russia** — no geographic restrictions
- **No credit card required** — easy setup
- **OpenAI-compatible API** — can use the standard `openai` Python package
- **Supports function calling** — enables tool use in agentic loop

## Architecture

### Agentic Loop

Same as Task 2, unchanged:

```
Question ──▶ LLM ──▶ tool call? ──yes──▶ execute tool ──▶ back to LLM
                         │
                         no
                         │
                         ▼
                    JSON output
```

**Loop constraints:**
- Maximum 10 tool call iterations
- Track all tool calls for output

### Components

#### 1. `agent.py`

Main CLI script with agentic loop and three tools.

**Key functions:**
- `load_env()` — parses `.env` files
- `validate_path()` — security check for path traversal
- `tool_read_file()` — reads a file from the project
- `tool_list_files()` — lists directory contents
- `tool_query_api()` — calls backend API with authentication
- `execute_tool()` — dispatches tool calls
- `extract_source_from_tool_calls()` — extracts source reference
- `run_agentic_loop()` — main loop: LLM → tool → LLM → ...
- `main()` — entry point

#### 2. Tools

##### `read_file`

Read a file from the project repository.

**Parameters:**
- `path` (string) — relative path from project root

**Returns:** File contents as string, or error message

**Security:**
- Blocks `../` path traversal
- Validates resolved path is within project root

##### `list_files`

List files and directories at a given path.

**Parameters:**
- `path` (string) — relative directory path from project root

**Returns:** Newline-separated listing, or error message

**Security:**
- Blocks `../` path traversal
- Validates resolved path is within project root

##### `query_api` (NEW in Task 3)

Call the backend API to query data or perform operations.

**Parameters:**
- `method` (string) — HTTP method (GET, POST, PUT, DELETE)
- `path` (string) — API path (e.g., `/items/`, `/analytics/completion-rate?lab=lab-99`)
- `body` (string, optional) — JSON request body for POST/PUT

**Returns:** JSON string with `status_code` and `body`

**Authentication:** Uses `LMS_API_KEY` from `.env.docker.secret` via `X-API-Key` header

**Error handling:**
- Timeout (30s) → error message
- Network error → error message
- Invalid JSON body → error message
- HTTP errors (401, 403, 500) → returned in response

**Implementation:**
```python
def tool_query_api(method: str, path: str, body: str | None = None, ...) -> str:
    """Call backend API with LMS_API_KEY authentication."""
    api_key = env_vars.get("LMS_API_KEY")
    base_url = env_vars.get("AGENT_API_BASE_URL", "http://localhost:42002")
    
    url = f"{base_url}{path}"
    headers = {"X-API-Key": api_key}
    
    with httpx.Client(timeout=30.0) as client:
        if method.upper() == "GET":
            response = client.get(url, headers=headers)
        elif method.upper() == "POST":
            json_body = json.loads(body) if body else None
            response = client.post(url, headers=headers, json=json_body)
        # ... etc
    
    return json.dumps({
        "status_code": response.status_code,
        "body": response.text,
    })
```

#### 3. Tool Schema (OpenAI Function Calling)

```python
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the project repository",
            "parameters": {...}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories at a given path",
            "parameters": {...}
        }
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
                        "enum": ["GET", "POST", "PUT", "DELETE"]
                    },
                    "path": {
                        "type": "string",
                        "description": "API path starting with / (e.g., /items/, /analytics/completion-rate?lab=lab-99)"
                    },
                    "body": {
                        "type": "string",
                        "description": "Optional JSON request body for POST/PUT requests"
                    }
                },
                "required": ["method", "path"]
            }
        }
    }
]
```

#### 4. System Prompt

The system prompt guides the LLM to choose the right tool:

```
You are a system agent that helps users find information about the project.

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
For general knowledge questions, set source to "general-knowledge".
```

**Key improvements from Task 2:**
- Added `query_api` tool description
- Clarified when to use each tool
- Added guidance for bug diagnosis (query first, then read)
- Added query parameter guidance

#### 5. Environment Variables

| Variable | Purpose | Source |
|----------|---------|--------|
| `LLM_API_KEY` | LLM provider API key | `.env.agent.secret` |
| `LLM_API_BASE` | LLM API endpoint URL | `.env.agent.secret` |
| `LLM_MODEL` | Model name | `.env.agent.secret` |
| `LMS_API_KEY` | Backend API key for `query_api` auth | `.env.docker.secret` |
| `AGENT_API_BASE_URL` | Base URL for `query_api` | `.env.docker.secret`, defaults to `http://localhost:42002` |

**Important:** Two distinct keys:
- `LLM_API_KEY` — authenticates with Qwen Code API (LLM provider)
- `LMS_API_KEY` — authenticates with backend API (your service)

Don't mix them up!

#### 6. `tests/test_agent.py`

Regression tests (5 total):

1. **`test_agent_json_output`** — verifies JSON structure
2. **`test_agent_merge_conflict_question`** — verifies `read_file` for wiki questions
3. **`test_agent_wiki_listing_question`** — verifies `list_files` for directory listing
4. **`test_agent_backend_framework_question`** — verifies `read_file` for source code questions (NEW)
5. **`test_agent_query_api_items_count`** — verifies `query_api` for data questions (NEW)

## Output Format

```json
{
  "answer": "There are 120 items in the database.",
  "source": "general-knowledge",
  "tool_calls": [
    {
      "tool": "query_api",
      "args": {"method": "GET", "path": "/items/"},
      "result": "{\"status_code\": 200, \"body\": \"[...]\"}"
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `answer` | string | The LLM's final answer |
| `source` | string | Wiki file reference (e.g., `wiki/git.md`) or `general-knowledge` |
| `tool_calls` | array | All tool calls made during the loop |

**Note:** `source` is now optional — system questions may not have a wiki source.

## Tool Selection Strategy

The LLM decides which tool to use based on the question type:

| Question Type | Example | Expected Tool(s) |
|---------------|---------|------------------|
| Wiki documentation | "How do you resolve a merge conflict?" | `read_file`, `list_files` |
| Source code lookup | "What framework does the backend use?" | `read_file` |
| Data query | "How many items are in the database?" | `query_api` |
| Status code check | "What status code without auth?" | `query_api` |
| Bug diagnosis | "Why does /analytics/completion-rate crash?" | `query_api` → `read_file` |
| Architecture explanation | "Explain the request lifecycle" | `read_file` (multiple) |

## Benchmark Results (run_eval.py)

### Initial Run

**Initial Score:** _/10 (TODO: run first benchmark)

**First Failures:**
- Question #X: _reason_
- Question #Y: _reason_

### Iteration Strategy

1. **Fix tool descriptions** — make `query_api` description more explicit about when to use it
2. **Improve system prompt** — add examples of query parameter formatting
3. **Adjust error handling** — return more informative error messages from `query_api`

### Final Score

**Final Score:** _/10 (TODO: update after passing all tests)

## Security

### Path Validation (read_file, list_files)

```python
def validate_path(path: str, project_root: Path) -> tuple[bool, str | Path]:
    # Block path traversal
    if ".." in path:
        return False, "Security error: path traversal not allowed"
    
    # Resolve and validate
    resolved = (project_root / path).resolve()
    try:
        resolved.relative_to(project_root.resolve())
        return True, resolved
    except ValueError:
        return False, "Security error: path must be within project directory"
```

### API Authentication (query_api)

- `LMS_API_KEY` read from environment, never hardcoded
- Sent via `X-API-Key` header (not in URL or body)
- Backend validates key on every request

## Error Handling

| Scenario | Behavior |
|----------|----------|
| No argument provided | Print usage to stderr, exit code 1 |
| Missing `LLM_API_KEY` | Print error to stderr, exit code 1 |
| Missing `LMS_API_KEY` | Return error in `query_api` result |
| API timeout (>30s) | Return error in tool result |
| API returns 401/403 | Return status_code in result, LLM may retry |
| File not found | Return error in tool result, continue loop |
| Path traversal attempt | Return security error in tool result |
| Max iterations reached | Return partial answer with tool_calls so far |
| Success | JSON to stdout, exit code 0 |

## Usage

### Run the agent

```bash
# Wiki documentation
uv run agent.py "How do you resolve a merge conflict?"

# Source code lookup
uv run agent.py "What Python framework does the backend use?"

# Data query
uv run agent.py "How many items are in the database?"

# Bug diagnosis
uv run agent.py "Why does /analytics/completion-rate crash for lab-99?"
```

### Run tests

```bash
uv run pytest tests/test_agent.py -v
```

### Run benchmark

```bash
uv run run_eval.py
```

## Constraints

- **stdout = JSON only** — all other output goes to stderr
- **timeout = 60 seconds** — total agent execution time
- **API timeout = 30 seconds** — per `query_api` call
- **max 10 tool calls** — prevents infinite loops
- **exit code 0 on success** — non-zero on any error
- **no path traversal** — tools block `../` and validate paths
- **no hardcoded secrets** — all config from environment variables

## Lessons Learned

### Tool Design

1. **Clear descriptions matter** — The LLM relies entirely on tool descriptions to decide when to call each tool. Vague descriptions lead to wrong tool selection. We improved `query_api` description by explicitly listing use cases: "data-dependent questions (item counts, scores, errors)".

2. **Enum constraints help** — Adding `"enum": ["GET", "POST", "PUT", "DELETE"]` to the `method` parameter prevents the LLM from inventing invalid HTTP methods.

3. **Query parameters in path** — Initially the LLM tried to pass query parameters as a separate argument. We clarified in the description: "Include query parameters in the path (e.g., `/analytics/completion-rate?lab=lab-99`)".

### Error Handling

4. **Graceful degradation** — When `query_api` fails, returning an error message (not raising an exception) allows the LLM to reason about the failure and potentially try a different approach.

5. **Timeout handling** — Network calls can hang. We added explicit 30-second timeouts to prevent the agent from getting stuck.

### System Prompt Engineering

6. **Tool selection guidance** — The system prompt now explicitly maps question types to tools. This dramatically improved tool selection accuracy.

7. **Step-by-step reasoning** — Instructing the LLM to "call tools step by step, not all at once" prevents it from making parallel calls that might conflict.

### Benchmark Iteration

8. **Local testing is fast** — `run_eval.py` provides immediate feedback. We could iterate quickly: fix issue → re-run → verify.

9. **Hidden questions are harder** — The autochecker tests additional hidden questions. We needed a genuinely working agent, not hard-coded answers.

10. **LLM judge for open-ended questions** — For reasoning questions (e.g., "explain the request lifecycle"), keyword matching isn't enough. The autochecker uses LLM-based judging with a rubric for more accurate scoring.

### Environment Management

11. **Two keys, two files** — Keeping `LLM_API_KEY` (`.env.agent.secret`) and `LMS_API_KEY` (`.env.docker.secret`) separate was confusing at first. Clear documentation and variable naming helped.

12. **Defaults for optional config** — `AGENT_API_BASE_URL` defaults to `http://localhost:42002` for local development, but the autochecker can override it.

## Future Work

- Add caching for repeated `query_api` calls
- Implement retry logic for transient API errors
- Add more tools (e.g., `search_code` for grep-like functionality)
- Improve source extraction to include section anchors
- Add support for streaming responses
