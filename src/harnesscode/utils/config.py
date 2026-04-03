import os
from pathlib import Path

def get_global_harnesscode_dir():
    """Return the global harnesscode directory."""
    harnesscode_dir = Path.home() / ".harnesscode"
    harnesscode_dir.mkdir(parents=True, exist_ok=True)
    (harnesscode_dir / "projects").mkdir(exist_ok=True)
    return harnesscode_dir

def get_global_project_dir(project_id: str):
    """Return the global project data directory used for learning data."""
    project_dir = get_global_harnesscode_dir() / "projects" / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir

def get_project_config_file(project_dir: str = ""):
    """Return the project config path (`.harnesscode/config.yaml`)."""
    if not project_dir:
        project_dir = os.getcwd()
    return Path(project_dir) / ".harnesscode" / "config.yaml"

def get_learning_dir(project_id: str):
    """Return the learning data directory."""
    learning_dir = get_global_project_dir(project_id) / "learning"
    learning_dir.mkdir(parents=True, exist_ok=True)
    return learning_dir

def get_metrics_file(project_id: str):
    """Return the metrics file path."""
    return get_learning_dir(project_id) / "metrics.json"

def get_bug_knowledge_dir(project_id: str):
    """Return the bug knowledge base directory."""
    bug_dir = get_learning_dir(project_id) / "docs" / "solutions" / "bugs"
    bug_dir.mkdir(parents=True, exist_ok=True)
    return bug_dir


def get_language_from_config(project_dir: str = "") -> str:
    """Read the language setting from `.harnesscode/config.yaml`.

    Priority:
    1. `HARNESSCODE_LANGUAGE` environment variable
    2. `language` field in `config.yaml`
    3. default to `en`

    Returns:
        Language code: `en` or `zh`.
    """
    # 1. Environment variable wins.
    env_lang = os.environ.get("HARNESSCODE_LANGUAGE", "").strip().lower()
    if env_lang in ("en", "zh", "zh-cn", "zh_CN"):
        return "zh" if env_lang.startswith("zh") else "en"

    # 2. Read from config.yaml.
    config_path = get_project_config_file(project_dir)
    if config_path.exists():
        try:
            # Try YAML parsing first.
            import yaml
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            if config and isinstance(config, dict):
                lang = config.get("language", "").strip().lower()
                if lang in ("en", "zh", "zh-cn", "zh_CN"):
                    return "zh" if lang.startswith("zh") else "en"
        except ImportError:
            # Fall back to simple text parsing when YAML is unavailable.
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("language:"):
                            val = line.split(":", 1)[1].strip().strip('"').strip("'").lower()
                            if val in ("en", "zh", "zh-cn", "zh_CN"):
                                return "zh" if val.startswith("zh") else "en"
            except Exception:
                pass
        except Exception:
            pass

    # 3. Default.
    return "en"


def get_backend_from_config(project_dir: str = "") -> str:
    """Read the backend setting from `.harnesscode/config.yaml`.

    Priority:
    1. `HARNESSCODE_BACKEND` environment variable
    2. `backend` field in `config.yaml`
    3. default to `opencode`

    Returns:
        Backend name: `opencode` or `claude`.
    """
    # 1. Environment variable wins.
    env_backend = os.environ.get("HARNESSCODE_BACKEND", "").strip().lower()
    if env_backend in ("opencode", "claude"):
        return env_backend

    # 2. Read from config.yaml.
    config_path = get_project_config_file(project_dir)
    if config_path.exists():
        try:
            # Try YAML parsing first.
            import yaml
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            if config and isinstance(config, dict):
                backend = config.get("backend", "").strip().lower()
                if backend in ("opencode", "claude"):
                    return backend
        except ImportError:
            # Fall back to simple text parsing when YAML is unavailable.
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("backend:"):
                            val = line.split(":", 1)[1].strip().strip('"').strip("'").lower()
                            if val in ("opencode", "claude"):
                                return val
            except Exception:
                pass
        except Exception:
            pass

    # 3. Default.
    return "opencode"
