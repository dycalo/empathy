# Getting Started

## Installation

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (recommended package manager)

### Install with uv (Recommended)

```bash
git clone <repo-url>
cd empathy

# Create virtual environment and install dependencies
uv venv && source .venv/bin/activate
uv pip sync uv.lock
```

### Install with pip

```bash
pip install -e .
```

## Configuration

### API Key Setup

```bash
export EMPATHY_API_KEY="sk-ant-api03-xxxx..."

# Optional: Specify model (default: claude-haiku-4-5-20251001)
export EMPATHY_MODEL="claude-sonnet-4-5"

# Optional: Use proxy or relay service
export EMPATHY_BASE_URL="https://api.your-proxy.com"

# Optional: Disable therapist auto-observation (default: enabled)
export EMPATHY_CLINICAL_OBSERVATION=0
```

## Quick Start

### Start Interactive Session

Launch the TUI (Text User Interface) as therapist:

```bash
uv run empathy start --side therapist
```

In another terminal, join as client:

```bash
uv run empathy start --side client
```

### Choose Agent Type

**LangChain Agent (Default, Recommended):**
```bash
uv run empathy start --side therapist --use-langchain
```

Features:
- Automatic tool orchestration with ReAct reasoning
- Built-in retry mechanism (3 attempts, exponential backoff)
- Enhanced error handling and fallback
- Complete execution statistics and logging

**BaseAgent (Lightweight):**
```bash
uv run empathy start --side therapist --no-langchain
```

Features:
- Direct Anthropic API calls
- Minimal overhead
- Suitable for simple scenarios

### Generate Dialogue

In the TUI control panel, enter instructions:

```
hi
```
```
continue the conversation
```
```
show more anxiety
```

The agent generates a draft, then you can:
- **a** - Accept draft as-is
- **e** - Edit before submitting
- **r** - Reject and regenerate
- **h** - Type response yourself
- **Tab** - Refine instruction

### Release Floor

When done with your turn:

```
/done
```

This releases the floor so the other side can respond.

## Automatic Mode

Generate dialogue automatically without human confirmation:

```bash
uv run empathy run dialogues/session_001 --turns 20
```

All responses are auto-accepted and marked as `AGENT_AUTO` source.

## Next Steps

- [Architecture Overview](architecture.md) - Understand system design
- [Configuration Guide](configuration.md) - Set up three-tier config
- [Tools Reference](tools.md) - Learn system tools
- [Skills Guide](skills.md) - Create custom skills
- [Export Guide](export.md) - Export training data
