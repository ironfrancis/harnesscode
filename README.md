<p align="center">
  <img src="https://readme-typing-svg.demolab.com?font=Courier+New&weight=900&size=40&pause=1000&color=FF6A00&center=true&vCenter=true&repeat=true&width=400&lines=HARNESSCODE" alt="HARNESSCODE">
</p>

<p align="center">
  <em>AI-Powered Human-in-the-Loop Development Framework</em>
</p>

<p align="center">
  <a href="README_CN.md">简体中文</a> | <b>English</b>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#installation">Installation</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#commands">Commands</a> •
  <a href="#contributing">Contributing</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.8+-blue.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/OpenCode-supported-purple.svg" alt="OpenCode">
  <img src="https://img.shields.io/badge/Claude%20Code-supported-orange.svg" alt="Claude Code">
</p>

---

## Features

### 🚀 Fully Autonomous Development
With complete PRD and comprehensive tech specs, the entire development process runs autonomously - no human attendance required. Just set it up and let it run.

### 🔄 Human-in-the-Loop
Human-in-the-loop design philosophy - AI executes, humans decide. Every critical node can pause for human intervention, ensuring controllable and predictable development.

### 🛠️ Harness Architecture
Extensible Agent framework - Orchestrator, Coder, Tester, Fixer, Reviewer - five specialized agents collaborate through state files to drive the development loop.

### ⚡ Dual Engine Support
Supports both [OpenCode](https://opencode.ai) and [Claude Code](https://www.anthropic.com/claude-code), switch AI engine with one command.

### 🌐 Tech Stack Agnostic
Java/Spring Boot, Python, Node.js, React, Vue... Any tech stack, just define `tech-stack.md` to start.

---

## Installation

### Prerequisites

- Python 3.8+
- [OpenCode](https://opencode.ai) or [Claude Code](https://www.anthropic.com/claude-code) installed

### OpenCode Installation

**Windows**:
```powershell
scoop install opencode
# or
npm install -g opencode-ai
```

**macOS**:
```bash
brew install anomalyco/tap/opencode
# or
npm install -g opencode-ai
```

**Linux**:
```bash
curl -fsSL https://opencode.ai/install | bash
# or
npm install -g opencode-ai
```

### Claude Code Installation

```bash
npm install -g @anthropic-ai/claude-code
claude auth login
```

### HarnessCode Installation

**Windows**:
```powershell
python -m pip install --upgrade pip
python -m pip install -e .
hc --version
```

**macOS / Linux**:
```bash
python3 -m pip install --upgrade pip
python3 -m pip install -e .
hc --version
```

<details>
<summary>🔧 Common Issues</summary>

**Q: `hc` command not found**

Windows: Add Python Scripts directory to PATH
```powershell
python -c "import sysconfig; print(sysconfig.get_path('scripts'))"
# Add the output path to system PATH
```

macOS/Linux:
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

**Q: `externally-managed-environment` error**

Use venv:
```bash
python3 -m venv ~/.hc-venv
source ~/.hc-venv/bin/activate
pip install harnesscode
```

</details>

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Orchestrator                         │
│         Read State → Decide Next → Dispatch Agent       │
└─────────────────────┬───────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        │             │             │
        ▼             ▼             ▼
┌───────────┐  ┌───────────┐  ┌───────────┐
│  Coder    │  │  Tester   │  │  Fixer    │
│  Implement│  │   Test    │  │   Fix     │
└───────────┘  └───────────┘  └───────────┘
        │             │             │
        └─────────────┼─────────────┘
                      │
                      ▼
              ┌───────────┐
              │ Reviewer  │
              │  Review   │
              └───────────┘
```

### Agent Responsibilities

| Agent | Responsibility |
|-------|---------------|
| **Orchestrator** | Read project state, decide which agent to run next |
| **Initializer** | Project setup, check tech stack, generate feature_list |
| **Coder** | Implement feature code |
| **Tester** | Multi-layer testing: static analysis → unit test → compilation |
| **Fixer** | Fix issues based on test/review reports |
| **Reviewer** | Code compliance review |

### State Files

```
.your-project/
├── .harnesscode/                 # Runtime data (auto-generated)
│   ├── feature_list.json         # Feature list
│   ├── test_report.json          # Test report
│   ├── review_report.json        # Review report
│   ├── missing_info.json         # Blockers (need human action)
│   └── config.yaml               # Project config
├── input/                        # Input files
│   ├── prd/                      # PRD documents
│   │   └── tech-stack.md         # Tech stack definition (required)
│   └── techspec/                 # Tech spec files
└── dev-log.txt                   # Runtime log
```

### Input Files

#### `input/prd/` - PRD Documents

Contains product requirements and tech stack definition.

| File | Required | Description |
|------|----------|-------------|
| `tech-stack.md` | ✅ Yes | Tech stack definition. Filename must be exact, format is flexible |

The included `tech-stack.md` is an example (Java + React). Customize it for your project.

#### `input/techspec/` - Tech Spec Files

Code conventions and standards. Each file defines rules for a specific category.

**Java Specs** (use as reference or modify directly):
- `tech-spec-checkstyle.md` - Code style (Checkstyle)
- `tech-spec-entity.md` - Entity class conventions
- `tech-spec-dto.md` - DTO conventions
- `tech-spec-service.md` - Service layer conventions
- `tech-spec-controller.md` - Controller conventions
- `tech-spec-mapper.md` - MyBatis Mapper conventions
- `tech-spec-enum.md` - Enum conventions
- `tech-spec-exception.md` - Exception handling
- `tech-spec-response.md` - API response format
- `tech-spec-database.md` - Database conventions

**React/TypeScript Specs**:
- `tech-spec-react-component.md` - React component conventions
- `tech-spec-typescript.md` - TypeScript conventions
- `tech-spec-antd-usage.md` - Ant Design usage
- `tech-spec-api-request.md` - API request conventions
- `tech-spec-frontend-*.md` - Frontend routing, style, form, performance, security
- `tech-spec-redux.md` - State management
- `tech-spec-i18n.md` - Internationalization

---

## Commands

| Command | Description |
|---------|-------------|
| `hc init` | Initialize project config (interactive) |
| `hc start` | Start development loop |
| `hc status` | Show project status and metrics |
| `hc restore` | Restore config files from backup |
| `hc uninstall` | Uninstall HarnessCode |
| `hc config` | View or modify configuration settings |
| `hc --version` | Show version info |

### Options

```bash
hc init --backend claude    # Use Claude Code engine
hc start --backend opencode # Use OpenCode engine
```

### Configuration

```bash
hc config                   # View current configuration
hc config language zh       # Switch to Chinese
hc config language en       # Switch to English
hc config backend claude    # Set backend to Claude
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `HARNESSCODE_BACKEND` | Default AI engine (opencode/claude) |
| `HARNESSCODE_LANGUAGE` | Default language (en/zh) |
| `OPENCODE_PATH` | Custom opencode command path |
| `CLAUDE_PATH` | Custom claude command path |

---

## Project Structure

```
harnesscode/
├── pyproject.toml          # Package config
├── src/harnesscode/
│   ├── cli.py              # CLI entry
│   ├── infinite_dev.py     # Main loop script
│   ├── installer.py        # Init/uninstall module
│   ├── backend.py          # AI engine abstraction
│   ├── agents/             # Agent definitions
│   │   ├── orchestrator.md
│   │   ├── initializer.md
│   │   ├── coder.md
│   │   ├── tester.md
│   │   ├── fixer.md
│   │   └── reviewer.md
│   └── utils/              # Utility modules
└── input/                  # Input file examples
```

---

## Uninstall

```bash
# Clean agent files and config
hc uninstall

# Uninstall Python package
pip uninstall harnesscode
```

---

## Contributing

Contributions welcome! See [Contributing Guide](CONTRIBUTING.md).

### Development

```bash
git clone https://github.com/yzddp/harnesscode.git
cd harnesscode
python -m pip install -e .
```

---

## License

[MIT](LICENSE)

---

<p align="center">
  Made with ❤️ by <a href="https://github.com/yzddp">油炸电灯泡 (yzddp)</a>
</p>