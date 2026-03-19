# Task 2 Plan: The Documentation Agent

## Overview

Extend the Task 1 agent with tool calling capabilities and an agentic loop. The agent will be able to read wiki files to answer questions with proper source references.

## LLM Provider

**Provider:** Qwen Code API  
**Model:** `qwen3-coder-plus`  
**API Type:** OpenAI-compatible chat completions with function calling

## Tools

### 1. `read_file`

Read a file from the project repository.

**Parameters:**
- `path` (string) — relative path from project root

**Returns:** File contents as string, or error message

**Security:**
- Block `../` path traversal
- Only allow files within project root directory

### 2. `list_files`

List files and directories at a given path.

**Parameters:**
- `path` (string) — relative directory path from project root

**Returns:** Newline-separated listing of entries

**Security:**
- Block `../` path traversal
- Only allow directories within project root

## Tool Schema (OpenAI Function Calling)

```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the project repository",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path from project root"}
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
                    "path": {"type": "string", "description": "Relative directory path from project root"}
                },
                "required": ["path"]
            }
        }
    }
]
```

## Agentic Loop

```
1. Send user question + tool definitions to LLM
2. Parse response:
   - If tool_calls present:
     a. Execute each tool
     b. Append tool results as "tool" role messages
     c. Send back to LLM
     d. Repeat (max 10 iterations)
   - If no tool_calls:
     a. Extract final answer
     b. Determine source from tool calls
     c. Output JSON and exit
```

**Loop constraints:**
- Maximum 10 tool call iterations
- Track all tool calls for output

## System Prompt

The system prompt will instruct the LLM to:
1. Use `list_files` to discover wiki directory structure
2. Use `read_file` to read relevant wiki files
3. Include source reference (file path + section anchor) in the answer
4. Call tools step-by-step, not all at once
5. Stop when enough information is gathered

## Output Format

```json
{
  "answer": "Edit the conflicting file, choose which changes to keep, then stage and commit.",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
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

## Security

**Path validation:**
- Resolve path using `Path.resolve()`
- Check that resolved path starts with project root
- Reject any path containing `..`
- Reject absolute paths

## Error Handling

| Scenario | Behavior |
|----------|----------|
| File not found | Return error message in tool result |
| Path traversal attempt | Return security error |
| LLM API error | Log to stderr, exit code 1 |
| Max iterations reached | Return partial answer with tool_calls so far |
| No answer from LLM | Return empty answer with tool_calls |

## Tests

Add 2 regression tests:

1. **Test merge conflict question:**
   - Question: "How do you resolve a merge conflict?"
   - Expects: `read_file` in tool_calls, `wiki/git-workflow.md` in source

2. **Test wiki listing question:**
   - Question: "What files are in the wiki?"
   - Expects: `list_files` in tool_calls

## Implementation Steps

1. Create `plans/task-2.md` (this file)
2. Update `agent.py`:
   - Add tool functions (`read_file`, `list_files`)
   - Add tool schemas
   - Implement agentic loop
   - Update output format with `source` field
3. Update `AGENT.md`:
   - Document tools
   - Document agentic loop
   - Document system prompt
4. Add 2 tests to `tests/test_agent.py`
5. Test manually with wiki questions
6. Run all tests
