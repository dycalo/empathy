# Empathy 🧠💬

A controllable agent framework for generating and experimenting with psychological support dialogues through human-in-the-loop interaction.

Empathy enables researchers, therapists, and writers to generate, evaluate, and intervene in therapeutic conversations using large language models with a dual-agent system (Client/Therapist) and interactive command-line interface.

## ✨ Key Features

- **Three-Tier Architecture** (Global/User/Dialogue): Hierarchical configuration system for flexible role definition and scenario customization
- **LangChain Agent System**: Unified agent implementation with ReAct reasoning, automatic retry, and intelligent tool orchestration
- **Centralized Tool Registry**: Dynamic tool registration and management for system tools, skills, and MCP integrations
- **Human-in-the-Loop Control**: Accept, edit, or reject every generated response with complete training signal preservation
- **Automatic State Management**: Cybernetic feedback loops for client emotion tracking and therapist clinical observations
- **Modular Design**: Decoupled STATE (role), SKILL (behavior), and MCP (external data) components
- **Training Data Export**: Export conversations in SFT and RLHF formats for model fine-tuning

## 🚀 Quick Start

```bash
# Install
git clone https://github.com/yourusername/empathy.git
cd empathy
uv venv && source .venv/bin/activate
uv pip sync uv.lock

# Configure
export EMPATHY_API_KEY="sk-ant-api03-xxxx..."

# Start therapist side
python -m empathy.cli.main start --side therapist

# In another terminal, start client side
python -m empathy.cli.main start --side client
```

Once both sides connect, you can begin the dialogue. Type instructions in the command panel, and the agent will generate drafts for you to accept, edit, or reject.

## 📖 Documentation

- **[Installation Guide](docs/installation.md)**: Detailed setup instructions
- **[Usage Guide](docs/usage.md)**: TUI interface, commands, and workflows
- **[Architecture](docs/architecture.md)**: System design and components
- **[Configuration](docs/configuration.md)**: Three-tier config system
- **[Tools Reference](docs/tools.md)**: System tools API (speak, record, emotion_state, memory_manage)
- **[Training Data](docs/training.md)**: Export formats for SFT and RLHF

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Three-Tier Config                        │
├─────────────────────────────────────────────────────────────┤
│  Global Layer    → Universal principles & ethics            │
│  User Layer      → Character profiles & prototypes          │
│  Dialogue Layer  → Session-specific context                 │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                   LangChain Agent System                     │
├─────────────────────────────────────────────────────────────┤
│  LangChainAgent  → ReAct reasoning, tool orchestration      │
│  ToolRegistry    → Centralized tool management              │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    System Tools                              │
├─────────────────────────────────────────────────────────────┤
│  speak           → Submit dialogue turn                      │
│  record          → Clinical records (therapist)              │
│  emotion_state   → Emotion tracking (client)                 │
│  memory_manage   → User-level long-term memory (Neo4j)       │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                 Automatic State Management                   │
├─────────────────────────────────────────────────────────────┤
│  Client Emotion  → Auto-updated before each turn            │
│  Therapist Obs   → Auto-generated clinical observations     │
└─────────────────────────────────────────────────────────────┘
```

## 🎯 Use Cases

- **Research**: Generate training data for therapeutic dialogue models
- **Clinical Training**: Practice therapeutic techniques with controlled scenarios
- **Content Creation**: Develop realistic therapy dialogue for scripts or educational materials
- **Model Evaluation**: Test LLM performance on nuanced psychological interactions

## 📂 Project Structure

```
empathy/
├── empathy/
│   ├── agents/          # LangChain agent implementation and tool registry
│   ├── cli/             # TUI and command-line interface
│   ├── extensions/      # Skills, config, MCP loading
│   ├── modes/           # Session management
│   └── storage/         # Data persistence
├── examples/            # Skills, states, and config examples
├── docs/                # Detailed documentation
└── tests/               # Test suite
```

## 🤝 Contributing

```bash
# Run tests
.venv/bin/python -m pytest tests/ -v

# Core logic locations:
# - empathy/agents/           LangChain agent and tool registry
# - empathy/agents/tools/     System tools (speak, record, etc.)
# - empathy/modes/            Session management
# - empathy/extensions/       Skills, config, MCP
# - empathy/cli/              TUI interface
# - empathy/storage/          Data persistence
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 🔄 Recent Changes

**2026-05-04**

### System Tool Refactoring

- **speak**: Terminal marker changed from `__TERMINAL_SPEAK__:content` to XML `<terminal_speak>content</terminal_speak>`. Added empty-content validation.
- **listen (removed)**: The `listen` tool was deleted as it was fully redundant — `ContextBuilder.build_messages()` already provides the complete transcript to the agent.
- **context / session simplification**: Removed conversation window management. The full transcript is now passed directly; the agent decides its own focus scope without external summary injection.

### Long-Term Memory Migration: Dialogue-Level → User-Level + Neo4j

- **New storage layer** (`empathy/storage/`):
  - `memory_models.py` — `Memory` dataclass + `MemoryType` literal
  - `memory_repo.py` — `MemoryRepository` ABC + `InMemoryMemoryRepository` for testing/fallback
  - `neo4j_repo.py` — `Neo4jMemoryRepository` using the `neo4j` Python driver
    - Graph model: `(:User {user_id})-[:HAS_MEMORY]->(:Memory)`
    - Auto schema: unique constraint + Lucene full-text index `memory_content_index`
    - Singleton factory `get_memory_repository()`: auto-selects backend based on `NEO4J_URI` env var

- **memory_manage tool rewrite**:
  - No longer reads/writes JSON files (`<dialogue_dir>/.empathy/<side>/memories/` deprecated)
  - `create_memory_manage_tool(user_id)` — returns `None` when `user_id` is missing, disabling the tool
  - All operations go through the repository layer with user isolation enforced by the bound `user_id`

- **user_id propagation**:
  - `dialogue.yaml` fields `client_id` / `therapist_id` serve as the user-level memory key
  - `resolve_user_id()` parses config → injects into `LangChainAgent` → injects into `ToolRegistry` → conditionally registers memory tool
  - Same user's memories persist across all their dialogues

- **CLI dialogue filtering**: When `--client-id` or `--therapist-id` is specified, the dialogue list only shows matching (or unassigned) dialogues.

**v0.2.0** - Architecture Simplification
- Unified agent system: Migrated to LangChain-only implementation
- Centralized tool registry for better tool management
- Removed deprecated BaseAgent, ClientAgent, and TherapistAgent
- Improved error handling and logging
- Enhanced tool orchestration with ReAct reasoning

## 📜 License

MIT License

---

**Getting Started**: Read the [Installation Guide](docs/installation.md) and [Usage Guide](docs/usage.md) to begin using Empathy.
