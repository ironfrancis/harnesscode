#!/usr/bin/env python3
"""HarnessCode CLI.

Supports both OpenCode and Claude Code backends.
"""

import sys
import os

__version__ = "4.1.0"

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)


def extract_backend_arg():
    """Extract and remove the `--backend` argument from `sys.argv`.
    
    Returns:
        backend_name: str or None
    """
    backend_name = None
    args_to_remove = []
    
    for i, arg in enumerate(sys.argv):
        if arg == "--backend" and i + 1 < len(sys.argv):
            backend_name = sys.argv[i + 1]
            args_to_remove.extend([i, i + 1])
        elif arg.startswith("--backend="):
            backend_name = arg.split("=", 1)[1]
            args_to_remove.append(i)
    
    for i in sorted(args_to_remove, reverse=True):
        sys.argv.pop(i)
    
    return backend_name


def main():
    backend_name = extract_backend_arg()
    
    if len(sys.argv) < 2:
        print("HarnessCode v" + __version__)
        print("")
        print("Usage: hc [init|start|status|restore|uninstall] [--backend opencode|claude]")
        print("")
        print("Commands:")
        print("  init      Initialize project configuration (interactive)")
        print("  start     Start development loop")
        print("  status    Show project status and metrics")
        print("  restore   Restore config files from backup (before PR)")
        print("  uninstall Remove harnesscode agent files and config")
        print("")
        print("Options:")
        print("  --backend   Specify AI backend: opencode (default) or claude")
        print("  --version   Show version information")
        print("  --help      Show this help message")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command in ["--version", "-v", "version"]:
        print(f"harnesscode {__version__}")
        sys.exit(0)
    
    if command in ["--help", "-h", "help"]:
        print("HarnessCode - AI-assisted human-in-the-loop development framework")
        print("")
        print("Usage: hc [init|start|status|restore|uninstall] [--backend opencode|claude]")
        print("")
        print("Backends:")
        print("  opencode  Use OpenCode (opencode.ai) as AI engine (default)")
        print("  claude    Use Claude Code (Anthropic) as AI engine")
        print("")
        print("Examples:")
        print("  hc init                    # Auto-detect backend")
        print("  hc init --backend claude   # Force Claude Code backend")
        print("  hc start                   # Use backend from config")
        print("  hc start --backend claude  # Override backend for this run")
        sys.exit(0)
    
    from installer import check_and_initialize
    check_and_initialize(backend_name)
    
    if command == "init":
        from infinite_dev import init_project
        init_project(backend_name)
    
    elif command == "start":
        from infinite_dev import main as run_main
        run_main(backend_name)
    
    elif command == "status":
        from utils.project_id import get_or_create_project_id
        from utils.metrics import Metrics
        from utils.config import get_backend_from_config
        
        project_id = get_or_create_project_id(".")
        metrics = Metrics(".")
        current_backend = get_backend_from_config(".")
        
        print(f"Project ID: {project_id}")
        print(f"Backend: {current_backend}")
        print("")
        print("Agent success rates:")
        for agent in ["orchestrator", "coder", "tester", "fixer"]:
            rate = metrics.get_success_rate(agent)
            print(f"  {agent}: {rate:.1%}")
    
    elif command == "restore":
        from restore_config import main as restore_main
        restore_main()
    
    elif command == "uninstall":
        from installer import uninstall
        uninstall()
    
    else:
        print(f"Unknown command: {command}")
        print("Usage: hc [init|start|status|restore|uninstall] [--backend opencode|claude]")
        sys.exit(1)


if __name__ == "__main__":
    main()
