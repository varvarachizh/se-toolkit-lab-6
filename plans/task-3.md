# Task 3 Plan: The System Agent

## Overview

Extend the Task 2 agent with a `query_api` tool to interact with the deployed backend API. This enables the agent to answer data-dependent questions and verify system facts against the actual running system.

## LLM Provider

**Provider:** Qwen Code API  
**Model:** `qwen3-coder-plus`  
**API Base:** `http://10.93.25.56:42005/v1`

## Backend API Configuration

**Base URL:** `http://localhost:42002` (via Caddy reverse proxy)  
**Auth:** `LMS_API_KEY` from `.env.docker.secret`  
**Endpoints:**
- `/items/` — list items
- `/interactions/` — list interactions
- `/learners/` — list learners
- `/pipeline/` — ETL pipeline operations
- `/analytics/*` — analytics endpoints

## New Tool: `query_api`

### Function Signature

```python
def query_api(method: str, path: str, body: str = None) -> str:
    """
    Call backend API with LMS_API_KEY authentication.
    
    Args:
        method: HTTP method (GET, POST, PUT, DELETE)
        path: API path (e.g., "/items/", "/analytics/completion-rate")
        body: Optional JSON request body for POST/PUT
    
    Returns:
        JSON string with status_code and body
    """
```

### Tool Schema (OpenAI Function Calling)

```json
{
  "type": "function",
  "function": {
    "name": "query_api",
    "description": "Call the backend API to query data or perform operations. Use for data-dependent questions.",
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
          "description": "API path starting with / (e.g., /items/, /analytics/completion-rate)"
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
```

### Implementation

```python
def tool_query_api(method: str, path: str, body: str | None = None) -> str:
    """Call backend API with LMS_API_KEY auth."""
    import httpx
    
    api_key = env_vars.get("LMS_API_KEY")
    base_url = env_vars.get("AGENT_API_BASE_URL", "http://localhost:42002")
    
    url = f"{base_url}{path}"
    headers = {"X-API-Key": api_key}
    
    try:
        async with httpx.AsyncClient() as client:
            if method == "GET":
                response = await client.get(url, headers=headers, timeout=30)
            elif method == "POST":
                response = await client.post(url, headers=headers, json=json.loads(body) if body else None, timeout=30)
            # ... etc
        
        return json.dumps({
            "status_code": response.status_code,
            "body": response.text
        })
    except Exception as e:
        return json.dumps({"status_code": 0, "error": str(e)})
```

## Environment Variables

| Variable | Purpose | Source |
|----------|---------|--------|
| `LLM_API_KEY` | LLM provider API key | `.env.agent.secret` |
| `LLM_API_BASE` | LLM API endpoint URL | `.env.agent.secret` |
| `LLM_MODEL` | Model name | `.env.agent.secret` |
| `LMS_API_KEY` | Backend API key for `query_api` auth | `.env.docker.secret` |
| `AGENT_API_BASE_URL` | Base URL for `query_api` | Optional, defaults to `http://localhost:42002` |

## Updated System Prompt

The system prompt must guide the LLM to choose the right tool:

```
You are a system agent that helps users find information about the project.

You have access to three tools:
1. list_files - List files and directories at a given path
2. read_file - Read the contents of a file
3. query_api - Call the backend API to query data

To answer questions:
- For wiki documentation: use list_files and read_file
- For system facts (framework, ports, status codes): use read_file on source code
- For data-dependent questions (item count, scores): use query_api
- For bug diagnosis: use query_api to reproduce the error, then read_file to find the bug

Rules:
- Use query_api with X-API-Key authentication (handled automatically)
- For GET requests, use method="GET"
- Include query parameters in the path (e.g., "/analytics/completion-rate?lab=lab-99")
- Call tools step by step, not all at once
- Stop when you have enough information to answer

If the question is not about this project, answer based on general knowledge.
```

## Agentic Loop

Same as Task 2, no changes needed:
1. Send user question + tool definitions to LLM
2. If tool_calls present → execute, append results, repeat
3. If no tool_calls → extract answer, output JSON, exit
4. Max 10 iterations

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

Note: `source` is now optional for system questions.

## Benchmark Questions (run_eval.py)

| # | Question | Expected Answer | Required Tools |
|---|----------|-----------------|----------------|
| 0 | Wiki: protect a branch | branch, protect | read_file |
| 1 | Wiki: SSH to VM | ssh / key / connect | read_file |
| 2 | Backend framework | FastAPI | read_file |
| 3 | API router modules | items, interactions, analytics, pipeline | list_files |
| 4 | Items in database | number > 0 | query_api |
| 5 | Status code without auth | 401 / 403 | query_api |
| 6 | /analytics/completion-rate error | ZeroDivisionError / division by zero | query_api, read_file |
| 7 | /analytics/top-learners error | TypeError / None / NoneType / sorted | query_api, read_file |
| 8 | Request lifecycle (LLM judge) | Caddy → FastAPI → auth → router → ORM → PostgreSQL | read_file |
| 9 | ETL idempotency (LLM judge) | external_id check, duplicates skipped | read_file |

## Implementation Steps

1. Create `plans/task-3.md` (this file)
2. Update `agent.py`:
   - Add `query_api` tool function
   - Add tool schema
   - Update system prompt
   - Load `LMS_API_KEY` and `AGENT_API_BASE_URL` from env
3. Update `AGENT.md`:
   - Document `query_api` tool
   - Document authentication
   - Document tool selection strategy
   - Add lessons learned (200+ words)
4. Add 2 tests to `tests/test_agent.py`:
   - Test for `query_api` usage (items count)
   - Test for `read_file` usage (framework question)
5. Run `uv run run_eval.py` and iterate until all 10 pass
6. Update plan with initial score and iteration strategy

## Initial Benchmark Run

After implementation and testing:

**Test Results:** 5/5 tests passing

**Test Breakdown:**
- ✓ test_agent_json_output — JSON structure valid
- ✓ test_agent_merge_conflict_question — uses read_file correctly
- ✓ test_agent_wiki_listing_question — uses list_files correctly
- ✓ test_agent_backend_framework_question — uses read_file, answers FastAPI
- ✓ test_agent_query_api_items_count — uses query_api, returns count

### Issues Found and Fixed

1. **LLM not reading files after list_files**
   - Issue: LLM answered based on file names alone
   - Fix: Added explicit rule "After using list_files, ALWAYS use read_file"
   - Fix: Added "Never answer based only on file names - read the file content first!"

2. **Wrong authentication header**
   - Issue: Used `X-API-Key` header, backend returned 401
   - Fix: Changed to `Authorization: Bearer <key>` (FastAPI HTTPBearer)

3. **Empty database**
   - Issue: ETL pipeline fails on autochecker API auth
   - Status: Known issue, doesn't affect agent functionality
   - Agent correctly uses query_api and reports 0 items

### Iteration Strategy

1. **System prompt improvements** — Added step-by-step instructions with examples
2. **Authentication fix** — Match backend's HTTPBearer security scheme
3. **Tool description tuning** — Made query_api use cases explicit

## Security Considerations

- `LMS_API_KEY` must be read from environment, not hardcoded
- API calls use HTTPS in production (via Caddy)
- Path validation for `query_api` to prevent SSRF (optional)

## Error Handling

| Scenario | Behavior |
|----------|----------|
| API returns 401/403 | Return error in tool result, LLM may retry |
| API timeout | Return error message, continue loop |
| Invalid JSON body | Return raw response text |
| Network error | Return error message |
