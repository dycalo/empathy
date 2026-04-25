# CLI Commands Implementation Summary

## Completed Changes

### 1. Default to LangChain Agent

**File**: `empathy/cli/main.py`

**Change**:
```python
use_langchain: bool = typer.Option(
    True, "--use-langchain/--no-langchain", help="Use LangChain agent (default: True)"
)
```

**Impact**:
- LangChain agent is now the default
- Use `--no-langchain` to switch to BaseAgent
- Simplifies command: `empathy start --side therapist` (no need for `--use-langchain`)

### 2. New TUI Commands

**File**: `empathy/cli/commands/__init__.py`

Added two new commands to the registry:
- `/feedback` - Show feedback examples or stats
- `/tools` - Show tool usage statistics

### 3. /feedback Command Implementation

**File**: `empathy/cli/tui.py`

**Usage**:
- `/feedback` - Show recent rejected/edited drafts (last 10)
- `/feedback stats` - Show acceptance/rejection statistics
- `/feedback clear` - Clear all draft history (with confirmation)

**Output Examples**:

```
/feedback
[bold]Recent Feedback (last 10):[/bold]
  [red]❌ REJECTED:[/red] "Let's talk about your childhood..."
  [yellow]✏️ EDITED:[/yellow] "That sounds difficult..." → "That sounds really challenging..."

/feedback stats
[bold]Feedback Statistics:[/bold]
  Total drafts: 50
  Accepted: 30 (60.0%)
  Rejected: 10 (20.0%)
  Edited: 7 (14.0%)
  Pending: 3
```

### 4. /tools Command Implementation

**File**: `empathy/cli/tui.py`

**Usage**: `/tools`

**Output**:
```
[bold]Tool Usage Statistics:[/bold]
  Total API calls: 25
  Input tokens: 37,500
  Output tokens: 3,750
  Cached tokens: 20,000
  Avg latency: 2,500ms
  Total latency: 62,500ms
```

**Features**:
- Aggregates API usage across all drafts
- Shows token consumption (input/output/cached)
- Calculates average and total latency
- Formatted with thousands separators for readability

## Command Registry

Updated `COMMANDS` dictionary with new entries:
```python
"feedback": {
    "description": "Show feedback examples or stats. Usage: /feedback [stats|clear]",
    "usage": "/feedback [stats|clear]",
},
"tools": {
    "description": "Show tool usage statistics",
    "usage": "/tools",
},
```

## Benefits

1. **Feedback Visibility**: Users can see what drafts were rejected/edited and why
2. **Performance Monitoring**: Track token usage and API latency
3. **Quality Metrics**: Acceptance rate helps evaluate agent performance
4. **Cost Tracking**: Token usage helps estimate API costs
5. **Debugging**: Identify patterns in rejected drafts

## Integration with Existing Features

- Uses `DialogueSession.get_draft_history()` to access draft data
- Leverages extended Draft model fields (api_usage, outcome, final_content)
- Consistent with existing command patterns (/status, /context, /agent)
- Follows Rich markup conventions for colored output

## Future Enhancements (Not Implemented)

1. **Export Command**: `empathy export <dialogue_id>` for training data
2. **Feedback Filtering**: `/feedback --type rejected --last 20`
3. **Tool Breakdown**: Show individual tool call counts (listen, record, etc.)
4. **Time-based Stats**: `/tools --today` or `/tools --last-hour`
5. **Comparison**: Compare stats across multiple sessions

## Testing

All syntax checks passed:
- ✅ empathy/cli/tui.py
- ✅ empathy/cli/commands/__init__.py
- ✅ empathy/cli/main.py
