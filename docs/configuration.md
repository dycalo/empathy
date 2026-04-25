# Configuration Guide

## Three-Tier Configuration System

Empathy uses a hierarchical configuration system where settings cascade from global defaults to dialogue-specific overrides.

## Configuration Layers

### Global Layer (`~/.empathy/global/`)

Defines system-wide defaults for all dialogues.

```
~/.empathy/global/
├── client/
│   ├── CLIENT.md           # Universal client knowledge
│   ├── skills/             # Globally available skills
│   └── mcp.json            # Global MCP servers
└── therapist/
    ├── THERAPIST.md        # Universal therapist knowledge
    ├── skills/
    └── mcp.json
```

**CLIENT.md / THERAPIST.md:**
- Role guidelines
- Communication principles
- Ethical boundaries
- General behavioral patterns

### User Layer (`~/.empathy/users/`)

Defines reusable character archetypes or personas.

```
~/.empathy/users/
├── client_anxious/
│   ├── CLIENT.md           # Anxious client persona
│   └── config.yaml         # Enabled skills and tools
└── therapist_cbt/
    ├── THERAPIST.md        # CBT-focused therapist
    └── config.yaml
```

**config.yaml structure:**
```yaml
llm:
  model: claude-sonnet-4-5

enabled_skills:
  - cbt_cognitive_restructuring
  - anxiety_response

enabled_mcp_servers:
  - time
  - weather
```

### Dialogue Layer (`<project>/dialogues/<session>/`)

Defines session-specific context and overrides.

```
dialogues/session_001/
├── client/
│   └── CLIENT.md           # Session-specific client state
├── therapist/
│   └── THERAPIST.md        # Session-specific focus
└── dialogue.yaml           # Links to user archetypes
```

**dialogue.yaml structure:**
```yaml
client_id: client_anxious
therapist_id: therapist_cbt
```

## Configuration Precedence

Settings merge with later layers overriding earlier ones:

```
Global defaults
  ↓ merged with
User archetype
  ↓ merged with
Dialogue specifics
  ↓
Final configuration
```

## Creating User Archetypes

### Example: Anxious Client

**~/.empathy/users/client_anxious/CLIENT.md:**
```markdown
# Anxious Client Persona

## Background
- 28-year-old software engineer
- Generalized anxiety disorder
- Perfectionist tendencies
- Difficulty with uncertainty

## Presentation
- Speaks quickly when anxious
- Asks for reassurance frequently
- Catastrophizes potential outcomes
- Physical symptoms: tension, restlessness

## Therapy Goals
- Reduce worry and rumination
- Build distress tolerance
- Challenge catastrophic thinking
- Improve sleep quality
```

**~/.empathy/users/client_anxious/config.yaml:**
```yaml
llm:
  model: claude-haiku-4-5-20251001

enabled_skills:
  - anxiety_response
  - catastrophic_thinking
  - reassurance_seeking

enabled_mcp_servers: []
```

### Example: CBT Therapist

**~/.empathy/users/therapist_cbt/THERAPIST.md:**
```markdown
# CBT-Focused Therapist

## Therapeutic Approach
- Cognitive Behavioral Therapy framework
- Structured, goal-oriented sessions
- Collaborative empiricism
- Socratic questioning

## Techniques
- Cognitive restructuring
- Behavioral experiments
- Thought records
- Exposure hierarchies

## Style
- Warm but directive
- Psychoeducational
- Evidence-based
- Homework assignments
```

**~/.empathy/users/therapist_cbt/config.yaml:**
```yaml
llm:
  model: claude-sonnet-4-5

enabled_skills:
  - cbt_cognitive_restructuring
  - behavioral_activation
  - exposure_therapy

enabled_mcp_servers:
  - time
```

## Dialogue-Specific Configuration

### Example: First Session

**dialogues/session_001/dialogue.yaml:**
```yaml
client_id: client_anxious
therapist_id: therapist_cbt
```

**dialogues/session_001/client/CLIENT.md:**
```markdown
# Session 1 Context

## Current Crisis
- Major presentation at work next week
- Experiencing panic attacks
- Not sleeping well

## Immediate Concerns
- "What if I freeze during the presentation?"
- "Everyone will think I'm incompetent"
- Fear of being judged

## Emotional State
- Anxiety: 8/10
- Sleep deprivation
- Irritable with partner
```

**dialogues/session_001/therapist/THERAPIST.md:**
```markdown
# Session 1 Focus

## Assessment Goals
- Evaluate anxiety severity
- Assess safety (no self-harm risk identified)
- Understand triggers and patterns
- Build therapeutic alliance

## Intervention Plan
- Psychoeducation about anxiety
- Introduce thought records
- Teach grounding techniques
- Assign homework: daily thought log

## Session Structure
1. Check-in and agenda setting
2. Explore presentation anxiety
3. Introduce cognitive model
4. Practice thought record
5. Assign homework
```

## MCP Configuration

### Global MCP Servers

**~/.empathy/global/client/mcp.json:**
```json
{
  "mcpServers": {
    "time": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-time"],
      "env": {}
    }
  }
}
```

### User-Level MCP

**~/.empathy/users/therapist_cbt/config.yaml:**
```yaml
enabled_mcp_servers:
  - time
  - weather
```

Only servers listed in `enabled_mcp_servers` will be loaded, even if defined in global `mcp.json`.

## Skills Configuration

### Global Skills

Place skill files in:
- `~/.empathy/global/client/skills/`
- `~/.empathy/global/therapist/skills/`

### Enabling Skills

**In config.yaml:**
```yaml
enabled_skills:
  - cbt_cognitive_restructuring
  - dbt_distress_tolerance
```

### Skill Modes

**Always Active:**
```yaml
---
name: anxiety_baseline
mode: always
---
```
Injected into every agent turn automatically.

**Manual Trigger:**
```yaml
---
name: cbt_cognitive_restructuring
mode: manual
trigger: /cbt-restructure
---
```
Activated by typing `/cbt-restructure` in TUI.

## Environment Variables

### Required

```bash
export EMPATHY_API_KEY="sk-ant-api03-xxxx..."
```

### Optional

```bash
# Model selection (default: claude-haiku-4-5-20251001)
export EMPATHY_MODEL="claude-sonnet-4-5"

# API endpoint (for proxies or relay services)
export EMPATHY_BASE_URL="https://api.your-proxy.com"

# Disable therapist auto-observation (default: 1 = enabled)
export EMPATHY_CLINICAL_OBSERVATION=0
```

## Best Practices

### Global Layer
- Keep minimal and universal
- Define ethical boundaries
- Set safety guidelines
- Avoid specific scenarios

### User Layer
- Create reusable archetypes
- Document personality traits
- Specify therapeutic approach
- Enable relevant skills

### Dialogue Layer
- Focus on session-specific context
- Document current crisis
- Set session goals
- Override only what's needed

### Skill Organization
- One skill per file
- Clear clinical framework
- Evidence-based content
- Proper frontmatter metadata

### MCP Integration
- Test servers independently first
- Enable only needed servers
- Document tool purposes
- Handle failures gracefully

## Troubleshooting

### Skills Not Loading
- Check `enabled_skills` in config.yaml
- Verify skill file exists in skills/ directory
- Ensure frontmatter is valid YAML
- Check skill name matches filename

### MCP Tools Not Available
- Verify `enabled_mcp_servers` in config.yaml
- Check mcp.json syntax
- Test MCP server command manually
- Review startup logs for connection errors

### Configuration Not Applied
- Check layer precedence (dialogue > user > global)
- Verify file paths are correct
- Ensure YAML syntax is valid
- Restart session after config changes

## Example Configurations

See `examples/configs/` for complete working examples:
- `anxious-client.yaml`
- `cbt-therapist.yaml`
- `dbt-therapist.yaml`
