#!/usr/bin/env python3
"""HarnessCode AI backend abstraction layer.

Supports both OpenCode and Claude Code execution backends.
"""

import json
import os
import sys
import shutil
from pathlib import Path


# Claude Code agent frontmatter definitions.
CLAUDE_AGENT_FRONTMATTER = {
    "orchestrator": {
        "name": "harnesscode-orchestrator",
        "description": "Decision-maker agent that reads project state and decides next agent. Use when orchestrating the harnesscode development loop.",
    },
    "initializer": {
        "name": "harnesscode-initializer",
        "description": "One-time project setup agent that scans PRD docs and generates feature list. Use for harnesscode project initialization.",
    },
    "coder": {
        "name": "harnesscode-coder",
        "description": "Code implementation agent that picks pending features and implements them. Use for harnesscode coding tasks.",
    },
    "tester": {
        "name": "harnesscode-tester",
        "description": "Multi-layer testing agent (static analysis, unit test, compilation). Use for harnesscode testing tasks.",
    },
    "fixer": {
        "name": "harnesscode-fixer",
        "description": "Bug and violation fixing agent that reads test/review reports. Use for harnesscode fix tasks.",
    },
    "reviewer": {
        "name": "harnesscode-reviewer",
        "description": "Code review and compliance checking agent. Use for harnesscode code review tasks.",
    },
}


HARNESSCODE_AGENT_NAMES = ["orchestrator", "initializer", "coder", "tester", "fixer", "reviewer"]


def _get_harnesscode_prompt_path(agent_name: str) -> str:
    return f"{{file:~/.config/opencode/agents/harnesscode-{agent_name}.md}}"


def _migrate_legacy_harnesscode_agent_config(user_config: dict):
    """Migrate only harnesscode-owned legacy OpenCode agent aliases.

    This removes duplicate registration without touching user-defined unprefixed
    agents that do not point at HarnessCode-managed prompt files.
    """
    agents = user_config.get("agent")
    if not isinstance(agents, dict):
        return

    for agent_name in HARNESSCODE_AGENT_NAMES:
        legacy_key = agent_name
        prefixed_key = f"harnesscode-{agent_name}"
        legacy_value = agents.get(legacy_key)

        if not isinstance(legacy_value, dict):
            continue

        if legacy_value.get("prompt") != _get_harnesscode_prompt_path(agent_name):
            continue

        if prefixed_key not in agents:
            agents[prefixed_key] = legacy_value

        del agents[legacy_key]


class Backend:
    """Abstract base class for AI execution backends."""

    name = ""

    def get_command_path(self):
        """Return the CLI command path."""
        raise NotImplementedError

    def build_run_cmd(self, agent, prompt, model=None):
        """Build the command list used to run an agent."""
        raise NotImplementedError

    def get_config_dir(self):
        """Return the backend config directory path."""
        raise NotImplementedError

    def get_agents_dir(self):
        """Return the directory where agent files are installed."""
        raise NotImplementedError

    def install_agents(self, src_dir):
        """Install agent files and return the installed filenames."""
        raise NotImplementedError

    def merge_config(self, harnesscode_config):
        """Merge or write backend configuration when needed."""
        raise NotImplementedError

    def uninstall_agents(self):
        """Remove installed agent files and clean backend configuration."""
        raise NotImplementedError

    def is_installed(self):
        """Return whether the backend CLI is available."""
        raise NotImplementedError

    def is_agents_initialized(self):
        """Return whether agent files are already installed."""
        agents_dir = self.get_agents_dir()
        marker = agents_dir / "harnesscode-orchestrator.md"
        return marker.exists()

    def get_available_models(self):
        """Return the list of available models."""
        return []

    def get_install_hint(self):
        """Return backend-specific installation guidance."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# OpenCode Backend
# ---------------------------------------------------------------------------

class OpenCodeBackend(Backend):
    """OpenCode (`opencode.ai`) execution backend."""

    name = "opencode"

    def get_command_path(self):
        # 1. Environment variable override.
        if os.environ.get("OPENCODE_PATH"):
            return os.environ["OPENCODE_PATH"]

        # 2. Search on PATH.
        found = shutil.which("opencode")
        if found:
            return found

        # 3. Check common install locations per platform.
        home = Path.home()
        if sys.platform == "win32":
            candidates = [
                home / "AppData" / "Roaming" / "npm" / "opencode.cmd",
                home / "AppData" / "Local" / "npm-global" / "opencode.cmd",
                home / ".local" / "bin" / "opencode.exe",
                Path("C:/Program Files/nodejs/opencode.cmd"),
            ]
        else:
            candidates = [
                home / ".npm-global" / "bin" / "opencode",
                Path("/usr/local/bin/opencode"),
                Path("/opt/homebrew/bin/opencode"),
                home / ".local" / "bin" / "opencode",
                home / ".nvm" / "current" / "bin" / "opencode",
                home / ".volta" / "bin" / "opencode",
                home / ".bun" / "bin" / "opencode",
                Path("/usr/bin/opencode"),
            ]
            # nvm version directories.
            nvm_dir = home / ".nvm" / "versions" / "node"
            if nvm_dir.exists():
                for node_ver in sorted(nvm_dir.iterdir(), reverse=True):
                    p = node_ver / "bin" / "opencode"
                    if p.exists():
                        candidates.insert(0, p)
                        break
            # fnm version directories.
            fnm_dir = home / ".local" / "share" / "fnm" / "node-versions"
            if not fnm_dir.exists():
                fnm_dir = home / "Library" / "Application Support" / "fnm" / "node-versions"
            if fnm_dir.exists():
                for node_ver in sorted(fnm_dir.iterdir(), reverse=True):
                    p = node_ver / "installation" / "bin" / "opencode"
                    if p.exists():
                        candidates.insert(0, p)
                        break

        for path in candidates:
            if path.exists():
                return str(path)

        return "opencode"

    def build_run_cmd(self, agent, prompt, model=None):
        cmd_path = self.get_command_path()
        if sys.platform == "win32":
            cmd = ['cmd', '/c', cmd_path, 'run', '--agent', f'harnesscode-{agent}']
        else:
            cmd = [cmd_path, 'run', '--agent', f'harnesscode-{agent}']

        if model:
            cmd.extend(['--model', model])

        cmd.append(prompt)
        return cmd

    def get_config_dir(self):
        config_dir = Path.home() / ".config" / "opencode"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir

    def get_agents_dir(self):
        agents_dir = self.get_config_dir() / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        return agents_dir

    def install_agents(self, src_dir):
        """Copy agent markdown files into `~/.config/opencode/agents/`."""
        agents_dir = self.get_agents_dir()
        copied = []

        agent_mapping = {
            "orchestrator.md": "harnesscode-orchestrator.md",
            "initializer.md": "harnesscode-initializer.md",
            "coder.md": "harnesscode-coder.md",
            "tester.md": "harnesscode-tester.md",
            "fixer.md": "harnesscode-fixer.md",
            "reviewer.md": "harnesscode-reviewer.md",
        }

        for src_name, dst_name in agent_mapping.items():
            src_path = src_dir / src_name
            dst_path = agents_dir / dst_name
            if src_path.exists():
                shutil.copy2(src_path, dst_path)
                copied.append(dst_name)

        return copied

    def merge_config(self, harnesscode_config):
        """Merge harnesscode agent config into `opencode.json`."""
        config_path = self.get_config_dir() / "opencode.json"

        # Read the existing config first.
        user_config = {}
        if config_path.exists():
            try:
                user_config = json.loads(config_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, Exception):
                user_config = {}

        if "agent" not in user_config:
            user_config["agent"] = {}
        if "mcp" not in user_config:
            user_config["mcp"] = {}

        _migrate_legacy_harnesscode_agent_config(user_config)

        # Merge agent config.
        for agent_name, agent_config in harnesscode_config.get("agent", {}).items():
            if agent_name in user_config["agent"]:
                existing = user_config["agent"][agent_name]
                if isinstance(existing, dict) and isinstance(agent_config, dict):
                    merged = dict(existing)
                    for key, value in agent_config.items():
                        if key == "permission" and key in merged:
                            existing_perm = merged[key]
                            new_perm = value
                            if isinstance(existing_perm, dict) and isinstance(new_perm, dict):
                                merged_perm = dict(existing_perm)
                                for perm_key, perm_value in new_perm.items():
                                    if perm_key not in merged_perm:
                                        merged_perm[perm_key] = perm_value
                                    elif isinstance(merged_perm[perm_key], dict) and isinstance(perm_value, dict):
                                        for sub_key, sub_value in perm_value.items():
                                            if sub_key not in merged_perm[perm_key]:
                                                merged_perm[perm_key][sub_key] = sub_value
                                merged[key] = merged_perm
                            else:
                                merged[key] = new_perm
                        else:
                            merged[key] = value
                    user_config["agent"][agent_name] = merged
                else:
                    user_config["agent"][agent_name] = agent_config
            else:
                user_config["agent"][agent_name] = agent_config

        # Merge MCP config.
        for mcp_name, mcp_config in harnesscode_config.get("mcp", {}).items():
            user_config["mcp"][mcp_name] = mcp_config

        # Write updated config.
        config_path.write_text(
            json.dumps(user_config, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        return user_config

    def uninstall_agents(self):
        """Remove installed agent files and clean `opencode.json`."""
        agents_dir = self.get_agents_dir()
        removed = []
        for f in agents_dir.glob("harnesscode-*.md"):
            f.unlink()
            removed.append(f.name)

        # Clean `opencode.json`.
        config_path = self.get_config_dir() / "opencode.json"
        if config_path.exists():
            try:
                config = json.loads(config_path.read_text(encoding="utf-8"))
                if "agent" in config:
                    for agent_name in HARNESSCODE_AGENT_NAMES:
                        prefixed_name = f"harnesscode-{agent_name}"
                        if prefixed_name in config["agent"]:
                            del config["agent"][prefixed_name]
                            removed.append(f"config:{prefixed_name}")
                if "mcp" in config and "playwright" in config["mcp"]:
                    del config["mcp"]["playwright"]
                    removed.append("config:mcp/playwright")
                config_path.write_text(
                    json.dumps(config, indent=2, ensure_ascii=False),
                    encoding="utf-8"
                )
            except Exception:
                pass

        return removed

    def is_installed(self):
        # 1. Environment variable.
        if os.environ.get("OPENCODE_PATH"):
            p = os.environ["OPENCODE_PATH"]
            if os.path.isfile(p):
                return True

        # 2. Search on PATH.
        if shutil.which("opencode"):
            return True

        # 3. Common install locations.
        home = Path.home()
        if sys.platform == "win32":
            candidates = [
                home / "AppData" / "Roaming" / "npm" / "opencode.cmd",
                home / "AppData" / "Local" / "npm-global" / "opencode.cmd",
            ]
        else:
            candidates = [
                home / ".npm-global" / "bin" / "opencode",
                Path("/usr/local/bin/opencode"),
                Path("/opt/homebrew/bin/opencode"),
                home / ".local" / "bin" / "opencode",
                home / ".volta" / "bin" / "opencode",
                home / ".bun" / "bin" / "opencode",
            ]
            nvm_dir = home / ".nvm" / "versions" / "node"
            if nvm_dir.exists():
                for node_ver in sorted(nvm_dir.iterdir(), reverse=True):
                    p = node_ver / "bin" / "opencode"
                    if p.exists():
                        return True

        for path in candidates:
            if path.exists():
                return True

        return False

    def get_available_models(self):
        config_path = self.get_config_dir() / "opencode.json"
        if not config_path.exists():
            return []
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            models = []
            providers = config.get("provider", {})
            disabled = config.get("disabled_providers", [])
            for provider_name, provider_data in providers.items():
                if provider_name in disabled:
                    continue
                provider_models = provider_data.get("models", {})
                for model_name in provider_models.keys():
                    models.append({
                        "id": f"{provider_name}/{model_name}",
                        "provider": provider_name,
                        "model": model_name,
                    })
            return models
        except Exception:
            return []

    def get_install_hint(self):
        lines = [
            "",
            "=" * 60,
            "  [ERROR] opencode is not installed or not in PATH",
            "",
            "  Please install opencode:",
        ]
        if sys.platform == "win32":
            lines += [
                "    scoop install opencode",
                "      or",
                "    choco install opencode",
                "      or",
                "    npm install -g opencode-ai",
            ]
        elif sys.platform == "darwin":
            lines += [
                "    brew install anomalyco/tap/opencode",
                "      or",
                "    npm install -g opencode-ai",
            ]
        else:
            lines += [
                "    npm install -g opencode-ai",
                "      or",
                "    curl -fsSL https://opencode.ai/install | bash",
            ]
        lines += [
            "",
            "  After installation, restart your terminal and retry.",
            "",
            "  If still not working, set the path manually:",
        ]
        if sys.platform == "win32":
            lines.append("    set OPENCODE_PATH=C:\\path\\to\\opencode.cmd")
        else:
            lines.append("    export OPENCODE_PATH=$(which opencode)")
        lines += ["=" * 60, ""]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Claude Code Backend
# ---------------------------------------------------------------------------

class ClaudeCodeBackend(Backend):
    """Claude Code (`claude`) execution backend."""

    name = "claude"

    def get_command_path(self):
        # 1. Environment variable override.
        if os.environ.get("CLAUDE_PATH"):
            return os.environ["CLAUDE_PATH"]

        # 2. Search on PATH.
        found = shutil.which("claude")
        if found:
            return found

        # 3. Check common install locations per platform.
        home = Path.home()
        if sys.platform == "win32":
            candidates = [
                home / "AppData" / "Local" / "Programs" / "claude-code" / "claude.exe",
                home / "AppData" / "Roaming" / "npm" / "claude.cmd",
                home / "AppData" / "Local" / "npm-global" / "claude.cmd",
                home / ".local" / "bin" / "claude.exe",
            ]
        elif sys.platform == "darwin":
            candidates = [
                Path("/usr/local/bin/claude"),
                Path("/opt/homebrew/bin/claude"),
                home / ".local" / "bin" / "claude",
                home / ".npm-global" / "bin" / "claude",
            ]
        else:
            candidates = [
                Path("/usr/local/bin/claude"),
                home / ".local" / "bin" / "claude",
                home / ".npm-global" / "bin" / "claude",
            ]
            # nvm version directories.
            nvm_dir = home / ".nvm" / "versions" / "node"
            if nvm_dir.exists():
                for node_ver in sorted(nvm_dir.iterdir(), reverse=True):
                    p = node_ver / "bin" / "claude"
                    if p.exists():
                        candidates.insert(0, p)
                        break

        for path in candidates:
            if path.exists():
                return str(path)

        return "claude"

    def build_run_cmd(self, agent, prompt, model=None):
        cmd_path = self.get_command_path()
        # Claude Code agent names use the `harnesscode-` prefix.
        agent_name = f"harnesscode-{agent}"

        if sys.platform == "win32":
            cmd = ['cmd', '/c', cmd_path, '--agent', agent_name, '-p']
        else:
            cmd = [cmd_path, '--agent', agent_name, '-p']

        cmd.append(prompt)

        if model:
            cmd.extend(['--model', model])

        # `--dangerously-skip-permissions`: required for unattended automation.
        # `--output-format stream-json --verbose`: stream JSON events in real time
        # so tool calls, results, and assistant messages all emit output promptly,
        # avoiding idle timeouts caused by delayed default `-p` output.
        cmd.extend([
            '--dangerously-skip-permissions',
            '--permission-mode', 'bypassPermissions',
            '--no-session-persistence',
            '--verbose',
            '--output-format', 'stream-json',
        ])
        return cmd

    def get_config_dir(self):
        config_dir = Path.home() / ".claude"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir

    def get_agents_dir(self):
        agents_dir = self.get_config_dir() / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        return agents_dir

    def install_agents(self, src_dir):
        """Read source markdown, add YAML frontmatter, and write to `~/.claude/agents/`."""
        agents_dir = self.get_agents_dir()
        copied = []

        agent_mapping = {
            "orchestrator.md": "harnesscode-orchestrator.md",
            "initializer.md": "harnesscode-initializer.md",
            "coder.md": "harnesscode-coder.md",
            "tester.md": "harnesscode-tester.md",
            "fixer.md": "harnesscode-fixer.md",
            "reviewer.md": "harnesscode-reviewer.md",
        }

        for src_name, dst_name in agent_mapping.items():
            src_path = src_dir / src_name
            dst_path = agents_dir / dst_name

            if not src_path.exists():
                continue

            # Read source file content.
            content = src_path.read_text(encoding="utf-8")

            # Derive the agent key by removing the `.md` suffix.
            agent_key = src_name.replace(".md", "")
            frontmatter = CLAUDE_AGENT_FRONTMATTER.get(agent_key, {})

            # Build the output with YAML frontmatter.
            fm_name = frontmatter.get("name", f"harnesscode-{agent_key}")
            fm_desc = frontmatter.get("description", f"HarnessCode {agent_key} agent")

            output = f"""---
name: {fm_name}
description: "{fm_desc}"
permissionMode: bypassPermissions
---

{content}"""

            dst_path.write_text(output, encoding="utf-8")
            copied.append(dst_name)

        return copied

    def merge_config(self, harnesscode_config):
        """Claude Code does not require a JSON config file for agents."""
        # If MCP config is needed later, it can be written to `.mcp.json`.
        # For now, no additional configuration is required.
        return {}

    def uninstall_agents(self):
        """Delete `~/.claude/agents/harnesscode-*.md`."""
        agents_dir = self.get_agents_dir()
        removed = []
        for f in agents_dir.glob("harnesscode-*.md"):
            f.unlink()
            removed.append(f.name)
        return removed

    def is_installed(self):
        # 1. Environment variable.
        if os.environ.get("CLAUDE_PATH"):
            p = os.environ["CLAUDE_PATH"]
            if os.path.isfile(p):
                return True

        # 2. Search on PATH.
        if shutil.which("claude"):
            return True

        # 3. Common install locations.
        home = Path.home()
        if sys.platform == "win32":
            candidates = [
                home / "AppData" / "Local" / "Programs" / "claude-code" / "claude.exe",
                home / "AppData" / "Roaming" / "npm" / "claude.cmd",
            ]
        elif sys.platform == "darwin":
            candidates = [
                Path("/usr/local/bin/claude"),
                Path("/opt/homebrew/bin/claude"),
                home / ".local" / "bin" / "claude",
            ]
        else:
            candidates = [
                Path("/usr/local/bin/claude"),
                home / ".local" / "bin" / "claude",
            ]

        for path in candidates:
            if path.exists():
                return True

        return False

    def get_available_models(self):
        """Return the preset model list supported by Claude Code."""
        return [
            {"id": "sonnet", "provider": "anthropic", "model": "sonnet"},
            {"id": "opus", "provider": "anthropic", "model": "opus"},
            {"id": "haiku", "provider": "anthropic", "model": "haiku"},
        ]

    def get_install_hint(self):
        lines = [
            "",
            "=" * 60,
            "  [ERROR] claude is not installed or not in PATH",
            "",
            "  Please install Claude Code:",
        ]
        if sys.platform == "win32":
            lines += [
                "    npm install -g @anthropic-ai/claude-code",
            ]
        elif sys.platform == "darwin":
            lines += [
                "    brew install claude-code",
                "      or",
                "    npm install -g @anthropic-ai/claude-code",
            ]
        else:
            lines += [
                "    npm install -g @anthropic-ai/claude-code",
            ]
        lines += [
            "",
            "  After installation, run 'claude auth login' to authenticate.",
            "",
            "  If still not working, set the path manually:",
        ]
        if sys.platform == "win32":
            lines.append("    set CLAUDE_PATH=C:\\path\\to\\claude.exe")
        else:
            lines.append("    export CLAUDE_PATH=$(which claude)")
        lines += ["=" * 60, ""]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Backend factory.
# ---------------------------------------------------------------------------

_BACKENDS = {
    "opencode": OpenCodeBackend,
    "claude": ClaudeCodeBackend,
}


def detect_backend():
    """Auto-detect installed AI backends and return the selected name."""
    oc = OpenCodeBackend()
    cc = ClaudeCodeBackend()

    oc_ok = oc.is_installed()
    cc_ok = cc.is_installed()

    if oc_ok and not cc_ok:
        return "opencode"
    if cc_ok and not oc_ok:
        return "claude"
    if oc_ok and cc_ok:
        # Both are installed; require the user to choose.
        return None
    # If neither is installed, default to `opencode` and show install guidance later.
    return "opencode"


def select_backend_interactive():
    """Interactively choose a backend when multiple options are available."""
    oc = OpenCodeBackend()
    cc = ClaudeCodeBackend()

    oc_ok = oc.is_installed()
    cc_ok = cc.is_installed()

    print("\nAvailable AI backends:")
    print("-" * 50)
    options = []
    if oc_ok:
        options.append(("opencode", "opencode (installed)"))
    else:
        options.append(("opencode", "opencode (not installed)"))
    if cc_ok:
        options.append(("claude", "claude   (installed)"))
    else:
        options.append(("claude", "claude   (not installed)"))

    for i, (_, label) in enumerate(options, 1):
        print(f"  [{i}] {label}")
    print("-" * 50)

    while True:
        try:
            choice = input("\nSelect a backend (enter number, default 1): ").strip()
            if not choice:
                return options[0][0]
            idx = int(choice)
            if 1 <= idx <= len(options):
                return options[idx - 1][0]
            else:
                print(f"Invalid number, please enter 1-{len(options)}")
        except ValueError:
            print("Please enter a valid number")
        except KeyboardInterrupt:
            print("\nCancelled")
            sys.exit(0)


def get_backend(name=None):
    """Return a backend instance.

    Priority:
    1. Explicit `name` argument
    2. `HARNESSCODE_BACKEND` environment variable
    3. Auto-detection
    4. Default to `opencode`
    """
    if not name:
        name = os.environ.get("HARNESSCODE_BACKEND", "")

    if not name:
        detected = detect_backend()
        name = detected if detected else "opencode"

    name = name.strip().lower()
    cls = _BACKENDS.get(name)
    if cls is None:
        print(f"[HarnessCode] Unknown backend: {name}, falling back to opencode")
        cls = OpenCodeBackend

    return cls()
