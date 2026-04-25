# Usage Guide

This guide covers how to use Empathy's interactive TUI (Text User Interface) and command-line tools.

## Starting a Session

### Interactive TUI Mode

Start the therapist side:
```bash
python -m empathy.cli.main start --side therapist
```

In another terminal, start the client side:
```bash
python -m empathy.cli.main start --side client
```

### Command Options

```bash
python -m empathy.cli.main start \
  --side therapist \          # Required: therapist or client
  --project /path/to/proj \   # Optional: project directory (default: current)
  --client-id my_client \     # Optional: use specific client profile
  --therapist-id my_therapist # Optional: use specific therapist profile
  --use-langchain             # Optional: use LangChain Agent (default)
  --no-langchain              # Optional: use lightweight BaseAgent
```

## TUI Interface

The TUI has two panels:
- **Left**: Control panel (instruction input, draft confirmation, logs)
- **Right**: Conversation transcript (real-time updates)

### Instruction Input

Type instructions in the input box to guide the agent:

| Input Type | Example | Agent Behavior |
|------------|---------|----------------|
| Greeting | `hi`, `hello` | Generate opening greeting |
| Continue | `continue`, `go ahead` | Naturally continue dialogue |
| Topic | `anxiety`, `reflect` | Generate response about topic |
| Specific | `ask about childhood` | Follow specific instruction |
| Slash command | `/done`, `/help` | Execute system command |

### Draft Confirmation

After the agent generates a draft, you can:

| Key | Action |
|-----|--------|
| `a` | **Accept** — Use draft as-is |
| `e` | **Edit** — Modify draft before submitting |
| `r` | **Reject** — Discard and try again |
| `h` | **Type yourself** — Skip agent, write manually |
| `Tab` | **Refine** — Return instruction to input for modification |
| `↑`/`↓` | Navigate options |
| `Enter` | Confirm selection |

### Floor System

The floor system prevents both sides from writing simultaneously:

- System automatically attempts to acquire floor on entry
- Only the floor holder can input instructions and generate drafts
- Type `/done` to release floor to the other side
- Status bar shows current floor holder:
  ```
  therapist │ floor: MINE │ turn: 3 │ model: claude-haiku-4-5-20251001 │ skills: 2
  ```

## Slash Commands

Type `/` and press `Tab` for autocomplete.

### Session Control
- `/done` — Release floor to other side
- `/quit` — Exit current session
- `/help` — List all commands
- `/status` — View floor and turn status

### Context Management
- `/context` — View context info (accepted/edited/rejected counts)
- `/context clear` — Reset context (agent re-reads history next call)

### Agent Information
- `/agent` — View current agent info (model, knowledge)
- `/agent model <id>` — Switch model dynamically
- `/skills` — List loaded skills
- `/session` — View full session info

### Feedback and Statistics
- `/feedback` — View recently rejected/edited drafts
- `/feedback stats` — Show acceptance/rejection/edit rates
- `/feedback clear` — Clear draft history (requires confirmation)
- `/tools` — View API usage stats (tokens, latency)

### Side-Specific Commands
- `/emotion` — View client's current emotional state (client only)
- `/observation` — View therapist's clinical observations (therapist only)

## Automatic Mode

Generate dialogue automatically without human confirmation:

```bash
python -m empathy.cli.main run \
  dialogues/session_001 \    # Dialogue directory path
  --turns 20 \               # Number of turns (default: 10)
  --model claude-haiku-4-5-20251001  # Model to use
```

All responses are marked with `AGENT_AUTO` source. Useful for quickly generating training data.

## Managing Dialogues

### List Dialogues
```bash
python -m empathy.cli.main start --side therapist
# Shows dialogue selection menu
```

### Delete Dialogue
```bash
python -m empathy.cli.main delete <dialogue-id>
python -m empathy.cli.main delete <dialogue-id> --force  # Skip confirmation
```

## Exporting Training Data

Export conversations for model fine-tuning or RLHF training.

### Export Formats

**SFT (Supervised Fine-Tuning)**:
- Source: `transcript.jsonl` (final dialogue)
- Purpose: Learn correct responses
- Contains: All accepted or edited turns

**RLHF (Reinforcement Learning from Human Feedback)**:
- Source: `transcript.jsonl` + `draft-history.jsonl`
- Purpose: Learn preferences (good vs. bad)
- Contains: chosen (transcript) vs. rejected (draft-history)

### Export Commands

```bash
# Export SFT data
python -m empathy.cli.main export session_001 --format sft

# Export RLHF data
python -m empathy.cli.main export session_001 --format rlhf

# Export both formats
python -m empathy.cli.main export session_001 --format sft,rlhf --output ./data

# Preview mode (don't write files)
python -m empathy.cli.main export session_001 --format rlhf --preview

# Include only rejected drafts (RLHF)
python -m empathy.cli.main export session_001 --format rlhf --include rejected

# Include rejected and edited drafts (RLHF)
python -m empathy.cli.main export session_001 --format rlhf --include rejected,edited
```

### Output Files

```
training_data/
├── session_001_sft.jsonl       # SFT data
├── session_001_rlhf.jsonl      # RLHF data
└── session_001_stats.json      # Statistics
```

### Data Format Examples

**SFT Format**:
```json
{
  "prompt": {
    "system": "You are the therapist...",
    "messages": [
      {"role": "user", "content": "[CLIENT]: I've been feeling anxious..."},
      {"role": "assistant", "content": "[THERAPIST]: Tell me more..."}
    ],
    "instruction": "validate their feelings"
  },
  "completion": "That sounds really challenging.",
  "metadata": {
    "dialogue_id": "session_001",
    "turn_number": 3,
    "source": "accepted"
  }
}
```

**RLHF Format**:
```json
{
  "prompt": {
    "system": "You are the therapist...",
    "messages": [
      {"role": "user", "content": "[CLIENT]: I've been feeling anxious..."}
    ],
    "instruction": "explore their anxiety"
  },
  "chosen": "Can you help me understand what triggers this?",
  "rejected": "Let's talk about your childhood.",
  "metadata": {
    "dialogue_id": "session_001",
    "turn_number": 5,
    "rejection_reason": "too directive"
  }
}
```

## Tips for Effective Use

### For Therapist Side
- Start with simple instructions like "hi" or "introduce yourself"
- Use `/skills` to see available therapeutic techniques
- Use `/observation` to check automatic clinical observations
- Review and edit drafts to ensure therapeutic appropriateness

### For Client Side
- Express emotions and thoughts naturally
- Use `/emotion` to check current emotional state
- Skills like `/defense` or `/catastrophize` can activate specific patterns
- Don't feel pressured to be a "perfect" client

### General Tips
- Use `/done` frequently to maintain natural turn-taking
- Review `/feedback stats` to track your editing patterns
- Use `/agent model` to switch models if responses aren't working
- Check `/tools` to monitor API usage and costs

## Troubleshooting

### Agent not responding
- Check that you have the floor (`/status`)
- Verify API key is set (`echo $EMPATHY_API_KEY`)
- Check logs in left panel for errors

### Can't acquire floor
- Other side may still hold it
- Wait for them to `/done` or check their status
- If stuck, restart both sides

### Drafts seem off-topic
- Use more specific instructions
- Check loaded skills with `/skills`
- Try `/context clear` to reset context
- Consider switching models with `/agent model`

### High API costs
- Use `claude-haiku-4-5-20251001` (default) for cost efficiency
- Monitor usage with `/tools`
- Use automatic mode for bulk generation

## Next Steps

- Learn about [Configuration](configuration.md) to customize profiles
- Explore [Tools Reference](tools.md) for LangChain Agent capabilities
- Read [Architecture](architecture.md) to understand the system design
