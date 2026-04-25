# Examples Directory

This directory contains comprehensive examples demonstrating how to use the Empathy framework.

## Directory Structure

```
examples/
├── skills/          # Skill definitions for both client and therapist
├── states/          # Three-tier STATE configuration examples
├── configs/         # Configuration file templates
└── README.md        # This file
```

## Skills

Skills define behavioral patterns (for clients) or therapeutic techniques (for therapists).

### Client Skills
- **defense-mechanism.md**: Unconscious psychological defense strategies
- **anxious-attachment.md**: Preoccupied attachment with fear of abandonment
- **avoidance-behavior.md**: Systematic avoidance maintaining anxiety
- **catastrophic-thinking.md**: Cognitive distortion predicting worst outcomes

### Therapist Skills
- **cbt-cognitive-restructuring.md**: Evidence-based CBT thought challenging
- **dbt-distress-tolerance.md**: DBT crisis survival skills (TIPP, ACCEPTS, IMPROVE)

## States (Three-Tier Architecture)

The STATE system uses a three-tier hierarchy where lower tiers override higher tiers:

### Global Tier (`states/global/`)
Foundation layer defining universal principles:
- **client/CLIENT.md**: Universal client behavior guidelines
- **therapist/THERAPIST.md**: Universal therapeutic principles and ethics

### User Tier (`states/users/`)
Specific character profiles:
- **client_anxious_professional/**: Sarah, a 32-year-old marketing manager with work anxiety
  - `CLIENT.md`: Detailed personality, background, patterns
  - `config.yaml`: Enabled skills and settings
- **therapist_cbt_oriented/**: Dr. Chen, CBT-specialized psychologist
  - `THERAPIST.md`: Therapeutic style, approach, competencies
  - `config.yaml`: Enabled skills and settings

### Dialogue Tier (`states/dialogue/`)
Session-specific context:
- **session_work_anxiety/**: Example session about presentation anxiety
  - `client/CLIENT.md`: Current situation, emotions, session goals
  - `therapist/THERAPIST.md`: Session plan, interventions, considerations
  - `dialogue.yaml`: Links to user profiles and session metadata

## Configuration Files

### config.yaml
User or dialogue-level configuration:
- Model selection
- Enabled skills
- Enabled MCP servers
- Metadata and tags

### dialogue.yaml
Links user profiles to specific dialogue:
- `client_id`: Which client profile to use
- `therapist_id`: Which therapist profile to use
- Session metadata (number, date, focus, phase)

### mcp.json
MCP server configuration:
- Server definitions (command, args, env)
- Examples: time, weather, filesystem, database, custom servers

## How to Use These Examples

### 1. Copy and Customize Skills
```bash
# Copy a skill to your global skills directory
cp examples/skills/anxious-attachment.md ~/.empathy/global/client/skills/

# Or create your own based on the template
```

### 2. Create User Profiles
```bash
# Copy example profile structure
cp -r examples/states/users/client_anxious_professional ~/.empathy/users/my_client

# Edit CLIENT.md and config.yaml to match your needs
```

### 3. Set Up a Dialogue
```bash
# In your project directory
mkdir -p dialogues/my_session/client
mkdir -p dialogues/my_session/therapist

# Copy dialogue-level STATE files
cp examples/states/dialogue/session_work_anxiety/client/CLIENT.md dialogues/my_session/client/
cp examples/states/dialogue/session_work_anxiety/therapist/THERAPIST.md dialogues/my_session/therapist/

# Create dialogue.yaml
cp examples/configs/dialogue.yaml dialogues/my_session/
# Edit to reference your user profiles
```

### 4. Configure MCP Servers
```bash
# Copy MCP config to global or user level
cp examples/configs/mcp.json ~/.empathy/global/client/

# Edit to add your API keys and server configurations
```

## Understanding the Merge Process

When you start a session, configurations merge in this order:

1. **Global** (`~/.empathy/global/client/CLIENT.md`)
2. **User** (`~/.empathy/users/client_anxious_professional/CLIENT.md`)
3. **Dialogue** (`dialogues/my_session/client/CLIENT.md`)

Lower tiers override higher tiers, so dialogue-specific context takes precedence.

## Example Workflow

```bash
# 1. Start with user profiles
python -m empathy.cli.main start --side therapist \
  --therapist-id therapist_cbt_oriented \
  --client-id client_anxious_professional

# 2. The system automatically merges:
#    - Global therapist guidelines
#    - Dr. Chen's CBT approach
#    - Session-specific plan (if dialogue-level STATE exists)

# 3. Skills are loaded based on config.yaml:
#    - Client: anxious_attachment, catastrophic_thinking
#    - Therapist: cbt_cognitive_restructuring

# 4. MCP servers connect if configured
```

## Creating Your Own Examples

### New Client Skill
1. Copy an existing skill as template
2. Research the psychological pattern
3. Include: description, presentation, therapeutic approach, examples
4. Add references to evidence base

### New User Profile
1. Define clear personality and background
2. Specify behavioral patterns and triggers
3. List cognitive distortions and core beliefs
4. Describe therapy responsiveness
5. Create matching config.yaml

### New Dialogue Context
1. Describe current situation and stressors
2. Define session goals (client and therapist perspectives)
3. Outline anticipated challenges
4. Plan interventions and homework
5. Link to user profiles in dialogue.yaml

## Tips for Quality Examples

- **Be specific**: Vague descriptions don't help the LLM generate authentic behavior
- **Include evidence**: Reference real psychological research and frameworks
- **Show patterns**: Demonstrate how behaviors manifest across situations
- **Balance depth and clarity**: Detailed but organized and scannable
- **Test iteratively**: Run sessions and refine based on agent behavior

## Contributing

When adding new examples:
1. Follow existing format and structure
2. Include proper frontmatter in skill files
3. Add references to evidence base
4. Test with actual sessions
5. Document any special considerations

---

For more information, see the main project README.md and docs/ directory.
