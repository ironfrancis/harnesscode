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

    # Initialize language from config
    from utils.config import get_language_from_config
    from utils.i18n import set_language, t, T
    set_language(get_language_from_config())

    if len(sys.argv) < 2:
        print(T("cli.version_header", version=__version__))
        print("")
        print(t("cli.usage"))
        print("")
        print(t("cli.commands"))
        print(t("cli.cmd_init"))
        print(t("cli.cmd_start"))
        print(t("cli.cmd_status"))
        print(t("cli.cmd_restore"))
        print(t("cli.cmd_uninstall"))
        print(t("cli.cmd_config"))
        print("")
        print(t("cli.options"))
        print(t("cli.opt_backend"))
        print(t("cli.opt_version"))
        print(t("cli.opt_help"))
        sys.exit(1)

    command = sys.argv[1]

    if command in ["--version", "-v", "version"]:
        print(f"harnesscode {__version__}")
        sys.exit(0)

    if command in ["--help", "-h", "help"]:
        print(t("cli.help_title"))
        print("")
        print(t("cli.usage"))
        print("")
        print(t("cli.backends"))
        print(t("cli.backend_opencode"))
        print(t("cli.backend_claude"))
        print("")
        print(t("cli.examples"))
        print(t("cli.ex_init_auto"))
        print(t("cli.ex_init_claude"))
        print(t("cli.ex_start"))
        print(t("cli.ex_start_claude"))
        sys.exit(0)

    # Handle config command
    if command == "config":
        handle_config()
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

        print(T("infinite_dev.project_id", id=project_id))
        print(T("infinite_dev.backend", backend=current_backend))
        print("")
        print(t("infinite_dev.success_rates"))
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
        print(T("cli.unknown_cmd", command=command))
        print(t("cli.usage"))
        sys.exit(1)


def handle_config():
    """Handle config view and modification commands."""
    from utils.config import (
        get_language_from_config,
        get_backend_from_config,
        get_project_config_file
    )
    from utils.i18n import t, T, set_language
    import os

    # Show current config if no subcommand
    if len(sys.argv) < 3:
        current_backend = get_backend_from_config(".")
        current_lang = get_language_from_config(".")
        
        print(t("cli.config_title"))
        print(t("cli.config_current"))
        print(T("cli.config_backend", backend=current_backend))
        print(T("cli.config_language", language=current_lang))
        print("")
        print(t("cli.config_help"))
        print(t("cli.config_examples"))
        print(t("cli.ex_config_lang"))
        print(t("cli.ex_config_lang_en"))
        print(t("cli.ex_config_backend"))
        return

    subcommand = sys.argv[2]

    if subcommand == "language" and len(sys.argv) >= 4:
        new_lang = sys.argv[3].lower()
        if new_lang not in ("en", "zh", "zh-cn", "zh_CN"):
            print(f"Invalid language: {new_lang}")
            print("Supported languages: en, zh")
            sys.exit(1)

        # Normalize language
        lang_code = "zh" if new_lang.startswith("zh") else "en"
        
        # Update config.yaml
        config_path = get_project_config_file(".")
        config_dir = os.path.dirname(config_path)
        os.makedirs(config_dir, exist_ok=True)

        # Read existing config
        config_data = {}
        if config_path.exists():
            try:
                import yaml
                with open(config_path, "r", encoding="utf-8") as f:
                    config_data = yaml.safe_load(f) or {}
            except ImportError:
                # Simple parsing without yaml
                with open(config_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if ":" in line:
                            key, val = line.split(":", 1)
                            config_data[key.strip()] = val.strip().strip('"').strip("'")

        # Update language
        config_data["language"] = lang_code

        # Write back
        try:
            import yaml
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
        except ImportError:
            with open(config_path, "w", encoding="utf-8") as f:
                for key, val in config_data.items():
                    f.write(f"{key}: {val}\n")

        set_language(lang_code)
        lang_name = "Chinese" if lang_code == "zh" else "English"
        print(f"Language set to {lang_name} ({lang_code})")
        print("语言已设置为中文" if lang_code == "zh" else "Language set to English")

    elif subcommand == "backend" and len(sys.argv) >= 4:
        new_backend = sys.argv[3].lower()
        if new_backend not in ("opencode", "claude"):
            print(f"Invalid backend: {new_backend}")
            print("Supported backends: opencode, claude")
            sys.exit(1)

        # Update config.yaml
        config_path = get_project_config_file(".")
        config_dir = os.path.dirname(config_path)
        os.makedirs(config_dir, exist_ok=True)

        # Read existing config
        config_data = {}
        if config_path.exists():
            try:
                import yaml
                with open(config_path, "r", encoding="utf-8") as f:
                    config_data = yaml.safe_load(f) or {}
            except ImportError:
                with open(config_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if ":" in line:
                            key, val = line.split(":", 1)
                            config_data[key.strip()] = val.strip().strip('"').strip("'")

        # Update backend
        config_data["backend"] = new_backend

        # Write back
        try:
            import yaml
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
        except ImportError:
            with open(config_path, "w", encoding="utf-8") as f:
                for key, val in config_data.items():
                    f.write(f"{key}: {val}\n")

        print(f"Backend set to {new_backend}")

    else:
        print(t("cli.config_help"))
        print(t("cli.config_examples"))
        print(t("cli.ex_config_lang"))
        print(t("cli.ex_config_lang_en"))
        print(t("cli.ex_config_backend"))


if __name__ == "__main__":
    main()
