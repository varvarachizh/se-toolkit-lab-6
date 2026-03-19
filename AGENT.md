# Agent Architecture (Task 1)

## Overview

This document describes the architecture of the simple CLI agent that connects to an LLM and returns structured JSON answers.

## LLM Provider

**Provider:** Qwen Code API  
**Model:** `qwen3-coder-plus`  
**API Type:** OpenAI-compatible chat completions endpoint

### Why Qwen Code?

- **1000 free requests per day** — sufficient for development and testing
- **Works from Russia** — no geographic restrictions
- **No credit card required** — easy setup
- **OpenAI-compatible API** — can use the standard `openai` Python package

## Architecture

```
┌─────────────────┐
│ User question   │ (sys.argv[1])
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    agent.py     │
│  - Parse input  │
│  - Load .env    │
│  - Call LLM     │
│  - Format JSON  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  OpenAI client  │ (timeout=60s)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Qwen Code API  │
│ qwen3-coder-plus│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  JSON response  │
│ {"answer": "...",│
│  "tool_calls":[]}│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    stdout       │ (JSON only)
└─────────────────┘
```

## Components

### 1. `agent.py`

Main CLI script located in the project root.

**Responsibilities:**
- Parse command-line argument (question)
- Load environment variables from `.env.agent.secret`
- Create OpenAI client with custom `base_url`
- Send chat completion request to LLM
- Format response as JSON
- Output JSON to stdout, logs to stderr

**Key functions:**
- `load_env()` — parses `.env` file format
- `main()` — entry point, handles argument validation and error handling

### 2. `.env.agent.secret`

Environment configuration file (gitignored).

**Required variables:**
```bash
LLM_API_KEY=your-api-key-here
LLM_API_BASE=http://<vm-ip>:<port>/v1
LLM_MODEL=qwen3-coder-plus
```

### 3. `tests/test_agent.py`

Single regression test that:
- Runs `agent.py` as a subprocess
- Parses stdout as JSON
- Verifies `answer` and `tool_calls` fields exist
- Checks that `answer` is non-empty and `tool_calls` is a list

## Output Format

```json
{"answer": "Representational State Transfer.", "tool_calls": []}
```

| Field | Type | Description |
|-------|------|-------------|
| `answer` | string | The LLM's response to the question |
| `tool_calls` | array | Empty for Task 1 (will be populated in Task 2) |

## Error Handling

| Scenario | Behavior |
|----------|----------|
| No argument provided | Print usage to stderr, exit code 1 |
| Missing `LLM_API_KEY` | Print error to stderr, exit code 1 |
| Missing `LLM_API_BASE` | Print error to stderr, exit code 1 |
| API timeout (>60s) | Print error to stderr, exit code 1 |
| API error | Print error to stderr, exit code 1 |
| Success | JSON to stdout, exit code 0 |

## Usage

### Run the agent

```bash
uv run agent.py "What does REST stand for?"
```

### Run tests

```bash
uv run pytest tests/test_agent.py -v
```

## Constraints

- **stdout = JSON only** — all other output goes to stderr
- **timeout = 60 seconds** — API calls must complete within this time
- **exit code 0 on success** — non-zero on any error
- **No tool calling yet** — `tool_calls` is always empty in Task 1

## Future Work (Tasks 2–3)

- **Task 2:** Add tool calling capability (e.g., `query_api`, `read_file`)
- **Task 3:** Implement agentic loop with tool execution and multi-turn reasoning
