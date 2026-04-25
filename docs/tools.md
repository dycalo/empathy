# System Tools Reference

## Overview

When using LangChain Agent (`--use-langchain`), agents can proactively call system tools to enhance dialogue generation. Tools are invoked automatically based on the agent's reasoning.

## Terminal Tools

### speak

**Purpose:** Submit dialogue turn for human confirmation

**Availability:** Both sides

**Parameters:**
- `content` (string, required) - Exact dialogue utterance

**Behavior:**
- Triggers human-in-the-loop confirmation flow
- User can Accept/Edit/Reject
- Only tool that produces output visible to other side

**Example:**
```python
speak(content="I understand you're feeling anxious about the presentation. Can you tell me more about what specifically worries you?")
```

**Agent Guidelines:**
- Always call `speak` when ready to respond
- Never call `speak` for clarification questions
- Content should be natural dialogue, no stage directions

## Query Tools

### listen

**Purpose:** Review conversation history

**Availability:** Both sides

**Parameters:**
- `scope` (string, required) - Query type: `recent`, `all`, `range`, `search`
- `limit` (integer, optional) - Number of turns to return (default: 5)
- `start_turn` (integer, optional) - Start of range (for `scope=range`)
- `end_turn` (integer, optional) - End of range (for `scope=range`)
- `keyword` (string, optional) - Search term (for `scope=search`)
- `speaker` (string, optional) - Filter by speaker: `therapist`, `client`, `both` (default: `both`)

**Examples:**

View recent conversation:
```python
listen(scope="recent", limit=3)
```

Search for keyword:
```python
listen(scope="search", keyword="anxiety", speaker="client")
```

View specific range:
```python
listen(scope="range", start_turn=5, end_turn=10)
```

View all history:
```python
listen(scope="all")
```

**Use Cases:**
- Recall earlier discussion points
- Search for specific topics
- Review client's previous statements
- Check therapeutic progress

## State Management Tools

### emotion_state (Client Only)

**Purpose:** Track and update emotional state

**Availability:** Client side only

**Parameters:**
- `action` (string, required) - Operation: `update`, `read`, `history`
- `primary_emotion` (string, optional) - Main emotion (for `action=update`)
- `intensity` (integer, optional) - Intensity 1-10 (for `action=update`)
- `triggers` (list, optional) - Triggering factors (for `action=update`)
- `physical_sensations` (list, optional) - Body sensations (for `action=update`)
- `thoughts` (string, optional) - Associated thoughts (for `action=update`)

**Examples:**

Update current state:
```python
emotion_state(
    action="update",
    primary_emotion="anxious",
    intensity=7,
    triggers=["upcoming presentation", "fear of judgment"],
    physical_sensations=["chest tightness", "rapid heartbeat"],
    thoughts="Everyone will think I'm incompetent"
)
```

Read current state:
```python
emotion_state(action="read")
```

View emotion history:
```python
emotion_state(action="history")
```

**Storage:** `.empathy/client/emotion-states/`

**Note:** Emotion state is also updated automatically before each client turn based on therapist's response. Manual tool calls supplement automatic updates.

### record (Therapist Only)

**Purpose:** Maintain clinical records

**Availability:** Therapist side only

**Parameters:**
- `action` (string, required) - Operation: `create`, `read`, `update`, `list`
- `record_type` (string, required) - Type: `assessment`, `progress_note`, `treatment_plan`, `observation`
- `content` (string, optional) - Record content (for `create`/`update`)
- `record_id` (string, optional) - Record identifier (for `read`/`update`)

**Examples:**

Create initial assessment:
```python
record(
    action="create",
    record_type="assessment",
    content="Client presents with moderate-severe anxiety symptoms. GAD-7 score: 15. Primary concerns: work performance, social evaluation. Strengths: insight, motivation for change."
)
```

Create progress note:
```python
record(
    action="create",
    record_type="progress_note",
    content="Session 3: Client practiced thought records this week. Reported reduced anxiety (7/10 → 5/10) when using cognitive restructuring. Homework: continue daily thought logs."
)
```

List all assessments:
```python
record(action="list", record_type="assessment")
```

Read specific record:
```python
record(action="read", record_type="progress_note", record_id="uuid")
```

**Storage:** `.empathy/therapist/records/`

**Record Types:**
- `assessment` - Initial evaluation, diagnosis, presenting problems
- `progress_note` - Session summaries, interventions used, client response
- `treatment_plan` - Goals, objectives, intervention strategies
- `observation` - Clinical observations, risk assessment, notable changes

### memory_manage

**Purpose:** Store and retrieve long-term memories

**Availability:** Both sides

**Parameters:**
- `action` (string, required) - Operation: `store`, `retrieve`, `search`, `update`, `delete`
- `memory_type` (string, required) - Type: `key_event`, `pattern`, `relationship`, `insight`
- `content` (string, optional) - Memory content (for `store`/`update`)
- `memory_id` (string, optional) - Memory identifier (for `retrieve`/`update`/`delete`)
- `query` (string, optional) - Search query (for `search`)
- `importance` (integer, optional) - Importance 1-10 (default: 5)

**Examples:**

Store key event:
```python
memory_manage(
    action="store",
    memory_type="key_event",
    content="Client disclosed childhood trauma related to public speaking - forced to give presentation in 3rd grade, classmates laughed",
    importance=9
)
```

Store pattern recognition:
```python
memory_manage(
    action="store",
    memory_type="pattern",
    content="Client consistently catastrophizes work situations but not personal relationships. Pattern suggests domain-specific cognitive distortion.",
    importance=7
)
```

Search memories:
```python
memory_manage(
    action="search",
    query="childhood trauma"
)
```

Retrieve specific memory:
```python
memory_manage(
    action="retrieve",
    memory_id="uuid"
)
```

**Storage:** `.empathy/<side>/memories/`

**Memory Types:**
- `key_event` - Significant disclosures, breakthroughs, crises
- `pattern` - Recurring themes, cognitive/behavioral patterns
- `relationship` - Interpersonal dynamics, attachment patterns
- `insight` - Client realizations, therapeutic progress

## Tool Call Patterns

### Therapist Typical Flow

```
1. listen(scope="recent", limit=3)
   → Review recent conversation

2. record(action="create", record_type="observation", content="...")
   → Document clinical observation

3. memory_manage(action="store", memory_type="pattern", content="...")
   → Store identified pattern

4. speak(content="...")
   → Respond to client
```

### Client Typical Flow

```
1. emotion_state(action="update", primary_emotion="anxious", intensity=7, ...)
   → Update emotional state

2. listen(scope="search", keyword="coping strategies")
   → Recall previous discussion

3. memory_manage(action="store", memory_type="insight", content="...")
   → Record personal insight

4. speak(content="...")
   → Respond to therapist
```

## Error Handling

**Tool Call Failures:**
- LangChain Agent automatically retries (up to 3 attempts)
- Exponential backoff between retries
- Falls back to BaseAgent if all retries fail
- Errors logged but don't crash session

**Invalid Parameters:**
- Tool returns error message
- Agent can adjust and retry
- User notified via UI logger

## Performance Considerations

**Tool Call Overhead:**
- Each tool call adds latency
- Use tools judiciously, not every turn
- Batch related operations when possible

**Storage Growth:**
- Memories and records accumulate over time
- Periodic cleanup recommended
- Search performance degrades with large datasets

## Best Practices

### When to Use Tools

**DO use tools when:**
- Need to recall specific information
- Documenting important clinical data
- Tracking emotional changes
- Storing insights for future reference

**DON'T use tools when:**
- Information is in immediate context
- Tool call would delay response unnecessarily
- Simple response doesn't require data lookup

### Tool Selection

**listen:**
- Use `scope=recent` for quick context refresh
- Use `scope=search` for specific topics
- Avoid `scope=all` unless necessary (performance)

**record vs memory_manage:**
- `record` - Formal clinical documentation
- `memory_manage` - Informal notes and patterns

**emotion_state:**
- Update when significant emotional shift occurs
- Don't update every turn (automatic system handles baseline)
- Use to express internal experience

## Troubleshooting

### Tools Not Available
- Verify using `--use-langchain` flag
- Check LangChain Agent initialization
- Review startup logs for errors

### Tool Calls Failing
- Check parameter types and required fields
- Verify storage directories exist
- Review error messages in logs

### Unexpected Tool Behavior
- Agent may call tools in unexpected order
- This is normal ReAct reasoning behavior
- Monitor with `--verbose` flag for debugging

## See Also

- [Architecture](architecture.md) - Tool system design
- [Getting Started](getting-started.md) - Enable LangChain Agent
- [Examples](examples/) - Tool usage examples
