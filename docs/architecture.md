# Architecture

## System Overview

Empathy is a controllable agent framework for psychological dialogue generation. It implements a bidirectional control loop where both client and therapist agents maintain dynamic internal states that influence their responses.

## Core Components

### 1. Dual Agent System

**BaseAgent**
- Direct Anthropic API integration
- Lightweight, minimal overhead
- Suitable for simple scenarios
- Fallback for LangChain failures

**LangChainAgent**
- ReAct reasoning with tool orchestration
- Automatic retry (3 attempts, exponential backoff)
- Enhanced error handling
- Complete execution tracking

### 2. Three-Tier Configuration

Configuration cascades from global defaults to dialogue-specific overrides:

```
Global Layer (~/. empathy/global/)
  ↓ overridden by
User Layer (~/.empathy/users/)
  ↓ overridden by
Dialogue Layer (<project>/dialogues/<session>/)
```

Each layer can define:
- Role knowledge and guidelines
- Active skills
- MCP tool configurations
- Model preferences

### 3. Control Theory Feedback Loop

**Client Side:**
```
Therapist speech → Emotion state analysis → State update → Prompt injection → Client response
```

**Therapist Side:**
```
Client response → Clinical observation → Observation update → Prompt injection → Therapist intervention
```

Both loops run automatically before each agent turn, creating dynamic, context-aware responses.

### 4. Context Window Management

**ConversationWindow** maintains a sliding buffer:
- Keeps last 6 turns verbatim (configurable)
- Older turns compressed into LLM-generated summary
- Summary updated incrementally as conversation grows
- Prevents context overflow while maintaining coherence

### 5. Human-in-the-Loop Control

Every agent-generated draft goes through confirmation:
- **Accept** - Use draft as-is
- **Edit** - Modify before committing
- **Reject** - Discard and regenerate

All decisions stored in `draft-history.jsonl` for training signal.

### 6. Floor System

Prevents concurrent writes:
- One side holds "floor" at a time
- Floor holder can generate drafts
- `/done` command releases floor
- Other side automatically notified

## Data Flow

```
Controller Instruction
  ↓
[Automatic State Update]
  ↓
Context Assembly (ContextBuilder)
  ├─ System Prompt (role, knowledge, skills, state)
  ├─ Messages (summary + windowed transcript)
  └─ Tools (speak, listen, record, emotion_state, memory_manage)
  ↓
Agent Generation (BaseAgent or LangChainAgent)
  ↓
Draft Creation
  ↓
Human Confirmation (Accept/Edit/Reject)
  ↓
Transcript Commit
```

## Storage Structure

```
dialogues/<session>/
├── transcript.jsonl              # Final committed turns
├── draft-history.jsonl           # All drafts with outcomes
└── .empathy/
    ├── state.json                # Floor state
    ├── client/
    │   ├── summary.json          # Conversation summary
    │   ├── emotion-states/       # Automatic emotion tracking
    │   │   ├── current.json
    │   │   └── history.jsonl
    │   └── memories/             # Long-term memory (LangChain)
    └── therapist/
        ├── summary.json
        ├── observations/         # Automatic clinical observations
        │   ├── current.json
        │   └── history.jsonl
        ├── records/              # Manual clinical records (LangChain)
        │   ├── assessments/
        │   ├── progress_notes/
        │   ├── treatment_plans/
        │   └── observations/
        └── memories/
```

## Tool System

### Terminal Tools
- **speak** - Submit dialogue turn (triggers human confirmation)

### Query Tools
- **listen** - Read conversation history (recent/all/range/search)

### State Management Tools
- **emotion_state** (client) - Track emotional state
- **record** (therapist) - Maintain clinical records
- **memory_manage** (both) - Store long-term memories

### MCP Tools
External tools via Model Context Protocol:
- Configured in `mcp.json` files
- Loaded asynchronously at startup
- Available to LangChain Agent

## Automatic State Management

### Client Emotion State
**Trigger:** Before each client turn
**Process:**
1. Read therapist's latest response
2. Analyze impact on client emotion (validation, challenge, exploration, tone)
3. Consider client personality and active skills
4. Generate new emotion state
5. Inject into client agent prompt

**State Dimensions:**
- Primary emotion and intensity (0-10)
- Physical sensations
- Thoughts
- Change direction (increasing/decreasing/stable)

### Therapist Clinical Observation
**Trigger:** Before each therapist turn (if enabled)
**Process:**
1. Read client's latest response
2. Read client emotion state (if available)
3. Analyze client presentation and emotional shift
4. Evaluate intervention effectiveness
5. Generate clinical observation
6. Inject into therapist agent prompt

**Observation Dimensions:**
- Client presentation
- Emotional shift (improving/worsening/stable)
- Therapeutic alliance (strong/establishing/strained)
- Intervention effectiveness
- Clinical focus areas
- Risk factors

## Extension Points

### Skills
Markdown files with frontmatter:
- `mode: always` - Auto-inject every turn
- `mode: manual` - Activate with trigger command
- Can include therapeutic frameworks, behavior patterns, etc.

### MCP Servers
External tool integration:
- Define in `mcp.json`
- Tools auto-discovered at startup
- Available to LangChain Agent

### Custom Agents
Subclass `BaseAgent`:
- Override `_role_preamble()` for custom system prompt
- Override `_invoke_tool()` for custom tool handling
- Maintain compatibility with `DialogueSession`

## Performance Considerations

**Prompt Caching:**
- Static system blocks marked `ephemeral`
- Cached by Anthropic across turns
- Reduces latency and cost

**Context Window:**
- Buffer size configurable (default: 6 turns)
- Summary generation only when needed
- Prevents token overflow

**Retry Strategy:**
- LangChain Agent: 3 attempts, exponential backoff
- Automatic fallback to BaseAgent on failure
- Graceful degradation

## Security

**API Key Management:**
- Environment variables only
- Never committed to version control
- Support for proxy/relay services

**Tool Safety:**
- All tools read-only except `speak`
- `speak` requires human confirmation
- No destructive operations

**Data Privacy:**
- All data stored locally
- No external transmission except LLM API
- Dialogue content under user control
