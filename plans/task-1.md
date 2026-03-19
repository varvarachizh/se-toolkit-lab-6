# Task 1 Plan: Call an LLM from Code

## LLM Provider and Model

**Provider:** Qwen Code API (deployed on VM)  
**Model:** `qwen3-coder-plus`  
**API Base:** `http://<vm-ip>:<port>/v1` (OpenAI-compatible endpoint)

### Why Qwen Code

- 1000 free requests per day
- Works from Russia
- No credit card required
- Compatible with OpenAI Python client

## Architecture

```
User question (sys.argv[1])
       ↓
agent.py (parse input, load .env)
       ↓
OpenAI-compatible API call (qwen3-coder-plus)
       ↓
JSON response: {"answer": "...", "tool_calls": []}
       ↓
stdout (valid JSON only)
```

## Components

### 1. Configuration (`.env.agent.secret`)

Environment variables read by the agent:

- `LLM_API_KEY` — API key for authentication
- `LLM_API_BASE` — base URL of the LLM API endpoint
- `LLM_MODEL` — model name (e.g., `qwen3-coder-plus`)

### 2. Agent (`agent.py`)

Main CLI script:

1. Read question from `sys.argv[1]`
2. Load environment variables from `.env.agent.secret`
3. Create OpenAI client with custom `base_url`
4. Send chat completion request (timeout=60s)
5. Parse LLM response and format JSON
6. Output JSON to stdout, all logs to stderr

### 3. Tests (`tests/test_agent.py`)

Single regression test:

- Run `agent.py` as a subprocess
- Parse stdout as JSON
- Verify `answer` field exists and is non-empty
- Verify `tool_calls` field exists (empty array for Task 1)

### 4. Documentation (`AGENT.md`)

Agent architecture documentation:

- Overview of how the agent works
- LLM provider choice and rationale
- How to run and test the agent

## Error Handling

| Scenario | Behavior |
|----------|----------|
| No argument provided | Print usage to stderr, exit code ≠ 0 |
| API error | Log error to stderr, exit code ≠ 0 |
| Success | JSON to stdout, exit code 0 |

## Output Format

```json
{"answer": "Representational State Transfer.", "tool_calls": []}
```

- `answer`: string — the LLM's response
- `tool_calls`: array — empty for Task 1 (will be populated in Task 2)

## Constraints

- Only valid JSON goes to stdout
- All debug/progress output goes to stderr
- API timeout: 60 seconds
- Exit code 0 on success
