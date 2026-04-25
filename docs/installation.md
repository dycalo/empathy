# Installation Guide

## Prerequisites

- Python 3.9 or higher
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- Anthropic API key

## Installation Steps

### 1. Clone the Repository

```bash
git clone <repo-url>
cd empathy
```

### 2. Set Up Virtual Environment

**Using uv (recommended)**:
```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip sync uv.lock
```

**Using pip**:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .
```

### 3. Configure API Key

```bash
export EMPATHY_API_KEY="sk-ant-api03-xxxx..."
```

To make this permanent, add it to your shell profile (`~/.bashrc`, `~/.zshrc`, etc.):
```bash
echo 'export EMPATHY_API_KEY="sk-ant-api03-xxxx..."' >> ~/.bashrc
source ~/.bashrc
```

## Optional Configuration

### Model Selection

```bash
# Default: claude-haiku-4-5-20251001
export EMPATHY_MODEL="claude-sonnet-4-5"
```

Available models:
- `claude-haiku-4-5-20251001` (default, fast and cost-effective)
- `claude-sonnet-4-5` (balanced performance)
- `claude-opus-4-6` (most capable)

### API Proxy or Relay

If using a proxy or relay service:
```bash
export EMPATHY_BASE_URL="https://api.your-proxy.com"
```

### Disable Automatic Clinical Observations

By default, therapist-side automatic clinical observations are enabled. To disable:
```bash
export EMPATHY_CLINICAL_OBSERVATION=0
```

## Verify Installation

```bash
# Check that the CLI is accessible
python -m empathy.cli.main --help

# You should see the command list
```

## Troubleshooting

### "Module not found" errors

Ensure you've activated the virtual environment:
```bash
source .venv/bin/activate
```

### API key not recognized

Verify the environment variable is set:
```bash
echo $EMPATHY_API_KEY
```

### Permission errors during installation

Try installing in editable mode:
```bash
pip install -e .
```

### uv not found

Install uv:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Or use pip instead (see step 2 above).

## Next Steps

- Read the [Usage Guide](usage.md) to learn how to use the TUI
- Explore [examples/](../examples/) for skill and state templates
- Review [Configuration](configuration.md) to customize your setup

## Updating

To update to the latest version:

```bash
git pull
uv pip sync uv.lock  # or: pip install -e . --upgrade
```

## Uninstallation

```bash
# Remove virtual environment
rm -rf .venv

# Remove cloned repository
cd ..
rm -rf empathy
```
