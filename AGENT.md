# Agent Architecture (Task 2)

## Overview

This document describes the architecture of the documentation agent that uses tools (`read_file`, `list_files`) to navigate the project wiki and answer questions with proper source references.

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

```
┌─────────────────┐
│ User question   │ (sys.argv[1])
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  System prompt  │ + tool definitions
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  LLM (Qwen)     │ → decides: tool call or answer?
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
  tools    no tools
    │         │
    ▼         ▼
┌─────────┐ ┌──────────────┐
│ Execute │ │ Final answer │
│  tool   │ │ Extract answer│
└────┬────┘ │ + source     │
     │      └──────┬───────┘
     │             │
     ▼             ▼
┌─────────┐   ┌──────────────┐
│ Append  │   │ JSON output  │
│ result  │   │ + exit 0     │
└────┬────┘   └──────────────┘
     │
     ▼
┌─────────────────┐
│ Back to LLM     │ (max 10 iterations)
└─────────────────┘
```

### Components

#### 1. `agent.py`

Main CLI script with agentic loop.

**Key functions:**
- `load_env()` — parses `.env.agent.secret`
- `validate_path()` — security check for path traversal
- `tool_read_file()` — reads a file from the project
- `tool_list_files()` — lists directory contents
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

#### 3. Tool Schema (OpenAI Function Calling)

```python
TOOLS = [
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
                        "description": "Relative path from project root"
                    }
                },
                "required": ["path"]
            }
        }
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
                        "description": "Relative directory path from project root"
                    }
                },
                "required": ["path"]
            }
        }
    }
]
```

#### 4. System Prompt

The system prompt instructs the LLM to:

1. Use `list_files` to explore the wiki directory structure
2. Use `read_file` to read relevant wiki files
3. Find the specific section that answers the question
4. Include source reference in format: `wiki/filename.md#section-anchor`
5. Call tools step by step, not all at once
6. Stop when enough information is gathered

**Full system prompt:**

```
You are a documentation agent that helps users find information in the project wiki.

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
and set source to "general-knowledge".
```

### 5. `.env.agent.secret`

Environment configuration file (gitignored).

**Required variables:**
```bash
LLM_API_KEY=your-api-key-here
LLM_API_BASE=http://<vm-ip>:<port>/v1
LLM_MODEL=qwen3-coder-plus
```

### 6. `tests/test_agent.py`

Regression tests:

1. **`test_agent_json_output`** — verifies JSON structure with `answer`, `tool_calls`, `source`
2. **`test_agent_merge_conflict_question`** — verifies `read_file` is used for merge conflict question
3. **`test_agent_wiki_listing_question`** — verifies `list_files` is used for wiki listing question

## Output Format

```json
{
  "answer": "Edit the conflicting file, choose which changes to keep, then stage and commit.",
  "source": "wiki/git-workflow.md",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"path": "wiki"},
      "result": "git-workflow.md\n..."
    },
    {
      "tool": "read_file",
      "args": {"path": "wiki/git-workflow.md"},
      "result": "..."
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `answer` | string | The LLM's final answer |
| `source` | string | Wiki file reference (e.g., `wiki/git.md`) |
| `tool_calls` | array | All tool calls made during the loop |

### Tool Call Structure

```json
{
  "tool": "read_file",
  "args": {"path": "wiki/git.md"},
  "result": "..."
}
```

## Agentic Loop Details

### Loop Flow

1. **Initialize** messages with system prompt + user question
2. **Send** to LLM with tool definitions
3. **Parse** response:
   - If `tool_calls` present → execute each tool, append results, go to step 2
   - If no `tool_calls` → extract answer, output JSON, exit
4. **Max iterations:** 10 (prevents infinite loops)

### Message Format

```python
messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": question},
    # After tool call:
    {"role": "assistant", "content": ..., "tool_calls": [...]},
    {"role": "tool", "tool_call_id": "...", "content": result},
    # ... repeat until final answer
]
```

## Security

### Path Validation

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

**Protections:**
- Blocks `../` in paths
- Validates resolved path is within project root
- Returns error message instead of raising exceptions

## Error Handling

| Scenario | Behavior |
|----------|----------|
| No argument provided | Print usage to stderr, exit code 1 |
| Missing `LLM_API_KEY` | Print error to stderr, exit code 1 |
| Missing `LLM_API_BASE` | Print error to stderr, exit code 1 |
| API timeout (>60s) | Print error to stderr, exit code 1 |
| API error | Print error to stderr, exit code 1 |
| File not found | Return error in tool result, continue loop |
| Path traversal attempt | Return security error in tool result |
| Max iterations reached | Return partial answer with tool_calls so far |
| Success | JSON to stdout, exit code 0 |

## Usage

### Run the agent

```bash
# Simple question (no tools needed)
uv run agent.py "What does REST stand for?"

# Wiki exploration
uv run agent.py "What files are in the wiki?"

# Documentation lookup
uv run agent.py "How do you resolve a merge conflict?"
```

### Run tests

```bash
uv run pytest tests/test_agent.py -v
```

## Constraints

- **stdout = JSON only** — all other output goes to stderr
- **timeout = 60 seconds** — API calls must complete within this time
- **max 10 tool calls** — prevents infinite loops
- **exit code 0 on success** — non-zero on any error
- **no path traversal** — tools block `../` and validate paths

## Future Work (Task 3)

- Add more tools (e.g., `query_api` to call the backend)
- Implement more sophisticated source extraction (section anchors)
- Add caching for repeated tool calls
- Improve system prompt for better tool selection
