# Empathy 🧠💬

A controllable agent framework for generating and experimenting with psychological support dialogues through human-in-the-loop interaction.

Empathy enables researchers, therapists, and writers to generate, evaluate, and intervene in therapeutic conversations using large language models with a dual-agent system (Client/Therapist) and interactive command-line interface.

## ✨ Key Features

- **Three-Tier Architecture** (Global/User/Dialogue): Hierarchical configuration system for flexible role definition and scenario customization
- **Dual Agent System**: Choose between lightweight BaseAgent or enhanced LangChainAgent with ReAct reasoning and automatic retry
- **Human-in-the-Loop Control**: Accept, edit, or reject every generated response with complete training signal preservation
- **Automatic State Management**: Cybernetic feedback loops for client emotion tracking and therapist clinical observations
- **Modular Design**: Decoupled STATE (role), SKILL (behavior), and MCP (external data) components
- **Training Data Export**: Export conversations in SFT and RLHF formats for model fine-tuning

## 🚀 Quick Start

```bash
# Install
git clone <repo-url>
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
- **[Tools Reference](docs/tools.md)**: System tools API (speak, listen, record, emotion_state, memory_manage)
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
│                      Agent System                            │
├─────────────────────────────────────────────────────────────┤
│  BaseAgent       → Lightweight, direct API calls            │
│  LangChainAgent  → ReAct reasoning, tool orchestration      │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    System Tools                              │
├─────────────────────────────────────────────────────────────┤
│  speak           → Submit dialogue turn                      │
│  listen          → Query conversation history                │
│  record          → Clinical records (therapist)              │
│  emotion_state   → Emotion tracking (client)                 │
│  memory_manage   → Long-term memory storage                  │
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
│   ├── agents/          # Agent implementations (BaseAgent, LangChainAgent)
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
# - empathy/agents/        Agent system
# - empathy/modes/         Session management
# - empathy/extensions/    Skills, config, MCP
# - empathy/cli/           TUI interface
# - empathy/storage/       Data persistence
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 📜 License

MIT License

---

**Getting Started**: Read the [Installation Guide](docs/installation.md) and [Usage Guide](docs/usage.md) to begin using Empathy.
