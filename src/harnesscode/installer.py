#!/usr/bin/env python3
"""HarnessCode installation and configuration bootstrap module.

Supports both OpenCode and Claude Code backends.
"""

import json
import os
import sys
import shutil
import subprocess
from pathlib import Path

script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from backend import get_backend, OpenCodeBackend


def get_harnesscode_agents_dir() -> Path:
    """Return the source agent directory bundled with harnesscode."""
    return Path(__file__).parent / "agents"


def get_harnesscode_config_template() -> dict:
    """Return the OpenCode configuration template."""
    harnesscode_permission = {
        "external_directory": {
            "~/.harnesscode/*": "allow"
        }
    }
    
    return {
        "agent": {
            "harnesscode-orchestrator": {
                "prompt": "{file:~/.config/opencode/agents/harnesscode-orchestrator.md}",
                "mode": "primary",
                "permission": harnesscode_permission
            },
            "harnesscode-initializer": {
                "prompt": "{file:~/.config/opencode/agents/harnesscode-initializer.md}",
                "mode": "primary",
                "permission": harnesscode_permission
            },
            "harnesscode-coder": {
                "prompt": "{file:~/.config/opencode/agents/harnesscode-coder.md}",
                "mode": "primary",
                "permission": harnesscode_permission
            },
            "harnesscode-tester": {
                "prompt": "{file:~/.config/opencode/agents/harnesscode-tester.md}",
                "mode": "primary",
                "permission": harnesscode_permission
            },
            "harnesscode-fixer": {
                "prompt": "{file:~/.config/opencode/agents/harnesscode-fixer.md}",
                "mode": "primary",
                "permission": harnesscode_permission
            },
            "harnesscode-reviewer": {
                "prompt": "{file:~/.config/opencode/agents/harnesscode-reviewer.md}",
                "mode": "primary",
                "permission": harnesscode_permission
            }
        },
        "mcp": {
            "playwright": {
                "type": "local",
                "command": ["npx", "@playwright/mcp@latest"],
                "enabled": True
            }
        }
    }


def is_initialized(backend=None) -> bool:
    """Check whether harnesscode agent files are installed for the backend."""
    if backend is None:
        backend = get_backend()
    return backend.is_agents_initialized()


def initialize(backend=None) -> bool:
    """Install agent files and configuration for the selected backend."""
    if backend is None:
        backend = get_backend()

    if is_initialized(backend):
        return True
    
    try:
        src_dir = get_harnesscode_agents_dir()
        copied_files = backend.install_agents(src_dir)

        # OpenCode requires an additional JSON config merge.
        if isinstance(backend, OpenCodeBackend):
            harnesscode_config = get_harnesscode_config_template()
            backend.merge_config(harnesscode_config)

        print(f"[HarnessCode] Initialized {backend.name} config with {len(copied_files)} agents")
        return True
    except Exception as e:
        print(f"[HarnessCode] Failed to initialize: {e}")
        return False


def get_harnesscode_gitignore_content() -> str:
    """Return the recommended harnesscode entries for `.gitignore`."""
    return """# HarnessCode runtime data
.harnesscode/
dev-log.txt
cycle-log.txt

# HarnessCode launcher scripts (should be installed globally via pip)
harnesscode
harnesscode.bat

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# IDE
.vscode/
.idea/
*.swp
*.swo

# Testing
.pytest_cache/
.coverage
htmlcov/

# System files
.DS_Store
Thumbs.db
"""


def update_gitignore(project_dir: str) -> None:
    """Update the project's `.gitignore` with harnesscode rules."""
    gitignore_path = os.path.join(project_dir, ".gitignore")
    
    harnesscode_rules = [
        "# HarnessCode runtime data",
        ".harnesscode/",
        "dev-log.txt",
        "cycle-log.txt",
        "",
        "# HarnessCode launcher scripts (should be installed globally via pip)",
        "harnesscode",
        "harnesscode.bat",
    ]
    
    existing_content = ""
    if os.path.exists(gitignore_path):
        try:
            with open(gitignore_path, "r", encoding="utf-8") as f:
                existing_content = f.read()
        except Exception:
            pass
    
    lines_to_add = []
    for rule in harnesscode_rules:
        if rule and rule not in existing_content:
            lines_to_add.append(rule)
    
    if lines_to_add:
        with open(gitignore_path, "a", encoding="utf-8") as f:
            if existing_content and not existing_content.endswith("\n"):
                f.write("\n")
            f.write("\n".join(lines_to_add) + "\n")
        print(f"[HarnessCode] Updated .gitignore with {len(lines_to_add)} rules")
    else:
        print("[HarnessCode] .gitignore already contains harnesscode rules")


def init_git_repo():
    """Initialize a Git repository in the current project if needed."""
    project_dir = os.getcwd()
    
    # 1. Check subdirectories for `.git` first.
    for entry in os.listdir(project_dir):
        entry_path = os.path.join(project_dir, entry)
        if os.path.isdir(entry_path):
            sub_git_dir = os.path.join(entry_path, ".git")
            if os.path.exists(sub_git_dir):
                print(f"[HarnessCode] Git repo found in subdirectory: {entry}, skipping root init")
                return False
    
    # 2. Check whether the current directory is already inside a Git repository.
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=10
        )
        if result.returncode == 0:
            print("[HarnessCode] Git repository already exists")
            update_gitignore(project_dir)
            return False
    except Exception:
        pass
    
    # 3. Check for `.git` in the current directory.
    git_dir = os.path.join(project_dir, ".git")
    if os.path.exists(git_dir):
        update_gitignore(project_dir)
        return False
    
    # 4. Only initialize when none of the checks found a repository.
    try:
        subprocess.run(["git", "init"], cwd=project_dir, check=True,
                       capture_output=True, encoding='utf-8', errors='replace')
        print("[HarnessCode] Initialized git repository")
        
        # 5. Create or update `.gitignore`.
        gitignore_path = os.path.join(project_dir, ".gitignore")
        if not os.path.exists(gitignore_path):
            with open(gitignore_path, "w", encoding="utf-8") as f:
                f.write(get_harnesscode_gitignore_content())
            print("[HarnessCode] Created .gitignore with harnesscode rules")
        else:
            update_gitignore(project_dir)
        
        return True
    except Exception as e:
        print(f"[HarnessCode] Failed to init git: {e}")
        return False


def check_and_install_dependencies():
    """Check for missing dependencies and install them if needed."""
    missing_deps = []
    
    # Check PyYAML.
    try:
        import yaml
    except ImportError:
        missing_deps.append("pyyaml")
    
    if missing_deps:
        print(f"[HarnessCode] Installing missing dependencies: {', '.join(missing_deps)}")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install"] + missing_deps,
                check=True,
                capture_output=True,
                encoding='utf-8',
                errors='replace'
            )
            print(f"[HarnessCode] Dependencies installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"[HarnessCode] Failed to install dependencies: {e}")
            print(f"[HarnessCode] Please install manually: pip install {' '.join(missing_deps)}")


def ensure_input_directories() -> None:
    """Ensure input/ directory structure exists, create or complete missing parts."""
    project_dir = os.getcwd()
    required_dirs = [
        os.path.join(project_dir, "input", "prd"),
        os.path.join(project_dir, "input", "techspec"),
    ]
    
    created = []
    for dir_path in required_dirs:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
            created.append(os.path.relpath(dir_path, project_dir))
    
    if created:
        print(f"[HarnessCode] Created input directories: {', '.join(created)}")
    else:
        print("[HarnessCode] Input directory structure already complete")


def check_and_initialize(backend_name=None) -> None:
    """Check and initialize the harnesscode environment.

    Args:
        backend_name: Explicit backend name (`opencode` or `claude`).
            If omitted, load it from config or auto-detect it.
    """
    check_and_install_dependencies()
    
    # If no backend was provided explicitly, load it from project config first.
    if not backend_name:
        from utils.config import get_backend_from_config
        backend_name = get_backend_from_config()
    
    backend = get_backend(backend_name)
    
    if not is_initialized(backend):
        print(f"[HarnessCode] First run detected, initializing for {backend.name}...")
        initialize(backend)
    
    ensure_input_directories()
    
    # Validate backend CLI availability before starting.
    if not backend.is_installed():
        print("")
        print("=" * 60)
        print(f"  [WARNING] {backend.name} command not found!")
        print("")
        print(f"  HarnessCode requires {backend.name} to run. Please install it:")
        print(backend.get_install_hint())
        print("=" * 60)
        print("")


def uninstall() -> None:
    """Uninstall harnesscode and clean local and optional global data."""
    from utils.config import get_backend_from_config
    
    print("[HarnessCode] Uninstalling...")
    
    # Read the current backend from config.yaml.
    project_dir = os.getcwd()
    backend_name = get_backend_from_config(project_dir)
    backend = get_backend(backend_name)
    
    # 1. Remove agent files and config for the current backend.
    removed = backend.uninstall_agents()
    if removed:
        print(f"[HarnessCode] Removed from {backend.name}: {', '.join(removed)}")
    
    # 2. Also clean the other backend if it has installed harnesscode agents.
    other_name = "claude" if backend.name == "opencode" else "opencode"
    other_backend = get_backend(other_name)
    if other_backend.is_agents_initialized():
        other_removed = other_backend.uninstall_agents()
        if other_removed:
            print(f"[HarnessCode] Also removed from {other_name}: {', '.join(other_removed)}")
    
    # 3. Remove the current project's `.harnesscode/` directory and `dev-log.txt`.
    harnesscode_local = os.path.join(project_dir, ".harnesscode")
    dev_log = os.path.join(project_dir, "dev-log.txt")
    
    if os.path.exists(harnesscode_local):
        shutil.rmtree(harnesscode_local)
        print(f"[HarnessCode] Removed {harnesscode_local}")
    
    if os.path.exists(dev_log):
        os.remove(dev_log)
        print(f"[HarnessCode] Removed {dev_log}")
    
    # 4. Ask whether to delete global data under `~/.harnesscode/`.
    global_harnesscode = Path.home() / ".harnesscode"
    if global_harnesscode.exists():
        print(f"")
        print(f"[HarnessCode] Global data directory: {global_harnesscode}")
        print(f"        This contains learning data and metrics for ALL projects.")
        answer = input("        Delete global data? (y/N): ").strip().lower()
        if answer == "y":
            shutil.rmtree(global_harnesscode)
            print(f"[HarnessCode] Removed {global_harnesscode}")
        else:
            print(f"[HarnessCode] Kept {global_harnesscode}")
    
    print("")
    print("[HarnessCode] Uninstall complete.")
    
    # 5. Ask whether to uninstall the Python package as well.
    print("")
    print("[HarnessCode] Do you also want to remove the harnesscode command?")
    answer_pkg = input("        Uninstall harnesscode package? (Y/n): ").strip().lower()
    if answer_pkg != "n":
        print("[HarnessCode] Uninstalling harnesscode package...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "uninstall", "harnesscode", "-y"],
                check=True,
                encoding='utf-8',
                errors='replace'
            )
            print("[HarnessCode] harnesscode package removed.")
            print("[HarnessCode] All clean! harnesscode has been completely removed.")
        except Exception as e:
            print(f"[HarnessCode] Failed to uninstall package: {e}")
            print("[HarnessCode] Please run manually:")
            print(f"        {sys.executable} -m pip uninstall harnesscode")
    else:
        print("[HarnessCode] Package kept. harnesscode command is still available.")
        print("[HarnessCode] To remove later: python -m pip uninstall harnesscode")
