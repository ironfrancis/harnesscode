#!/usr/bin/env python3
"""
HarnessCode - Main Loop Module
"""

import subprocess
import time
import random
import os
import re
import sys
import json
import shutil
import threading
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from utils.project_id import get_or_create_project_id
from utils.config import get_project_config_file, get_learning_dir, get_backend_from_config
from knowledge_manager import KnowledgeManager
from utils.metrics import Metrics
from backend import get_backend

try:
    import yaml
except ImportError:
    yaml = None

IDLE_TIMEOUT = 300
SELECTED_MODEL = None
current_backend = None


def kill_process_tree(pid):
    """Kill process tree (cross-platform)"""
    try:
        if sys.platform == "win32":
            subprocess.run(['taskkill', '/F', '/T', '/PID', str(pid)], 
                          capture_output=True, timeout=10)
        else:
            import signal
            os.killpg(os.getpgid(pid), signal.SIGTERM)
    except Exception:
        pass


project_dir = os.getcwd()
harnesscode_dir = os.path.join(project_dir, ".harnesscode")
log_file = os.path.join(project_dir, "dev-log.txt")
progress_file = os.path.join(harnesscode_dir, "claude-progress.txt")
feature_list_file = os.path.join(harnesscode_dir, "feature_list.json")
missing_info_file = os.path.join(harnesscode_dir, "missing_info.json")
test_report_file = os.path.join(harnesscode_dir, "test_report.json")
review_report_file = os.path.join(harnesscode_dir, "review_report.json")
cache_file = os.path.join(harnesscode_dir, "cache.json")

project_id = None
metrics = None
knowledge_mgr = None

SKIP_PATTERNS = [
    r'^Called the \w+ tool',
    r'^<path>',
    r'^<type>',
    r'^<content>',
    r'^\(End of file',
    r'^```',
    r'^output:',
    r'^result:',
    r'^exit_code:',
    r'^duration_ms:',
    r'^#\s*Tool Instructions',
    r'^#\s*Available Tools',
    r'^#\s*Environment',
    r'^#\s*Working directory',
    r'^Platform:',
    r'^Today\'s date:',
    r'^Is directory a git repo',
    r'^\s*\d+:\s*$',
    r'^\s*$',
]

last_feature_list = None


def get_webhook_url():
    config_path = get_project_config_file(project_dir)
    if os.path.exists(config_path):
        if yaml is not None:
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                if config and isinstance(config, dict):
                    url = config.get("webhook_url", "")
                    return url.strip() if url else ""
            except Exception:
                pass
        else:
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("webhook_url:"):
                            return line.split(":", 1)[1].strip().strip('"').strip("'")
            except Exception:
                pass
    return os.environ.get("HARNESSCODE_WEBHOOK_URL", "")


def log(message, to_file_only=False):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")
    if not to_file_only:
        print(f"[{timestamp}] {message}")


def log_cycle_detail(iteration, agent, args, duration, status, output_summary):
    """Record detailed information for each cycle to cycle-log.txt"""
    cycle_log_file = os.path.join(harnesscode_dir, "cycle-log.txt")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with open(cycle_log_file, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*80}\n")
        f.write(f"Cycle: {iteration}\n")
        f.write(f"Time: {timestamp}\n")
        f.write(f"Agent: {agent}\n")
        f.write(f"Args: {args}\n")
        f.write(f"Duration: {duration:.2f}s\n")
        f.write(f"Status: {status}\n")
        f.write(f"Output Summary:\n{output_summary}\n")
        f.write(f"{'='*80}\n")


def should_generate_report():
    """Check if there is enough work progress to generate a report"""
    data = read_feature_list()
    features = get_features_from_data(data) if data else []
    
    has_features = len(features) > 0
    has_completed = any(f.get("status") == "completed" for f in features)
    
    has_code_changes = False
    start_commit_result = subprocess.run(
        ["git", "rev-list", "--max-parents=0", "HEAD"],
        capture_output=True, text=True, encoding='utf-8', errors='replace',
        cwd=project_dir, timeout=10
    )
    if start_commit_result.returncode == 0:
        initial_commit = start_commit_result.stdout.strip()
        diff_result = subprocess.run(
            ["git", "diff", "--stat", initial_commit],
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            cwd=project_dir
        )
        has_code_changes = diff_result.returncode == 0 and diff_result.stdout.strip()
    
    return has_features or has_code_changes


def should_skip(line):
    stripped = line.strip()
    if not stripped:
        return True
    for pattern in SKIP_PATTERNS:
        if re.match(pattern, stripped):
            return True
    return False


def filter_and_print(line):
    if should_skip(line):
        return None
    print(line, end='', flush=True)
    return line


def parse_orchestrator_decision(output):
    match = re.search(r'---\s*ORCHESTRATOR\s+NEXT:\s*(\w+)(?:\s+(.+?))?\s*---', output, re.IGNORECASE)
    if match:
        agent = match.group(1).lower()
        args = match.group(2).strip() if match.group(2) else ""
        return agent, args
    
    if "PROJECT COMPLETE" in output.upper():
        return "complete", ""
    
    return None, None


def parse_agent_output_status(output, agent_type):
    match = re.search(r'---\s*AGENT\s+COMPLETE:\s*(\w+)\s*-\s*(\w+)\s*-\s*(\w+)\s*---', output, re.IGNORECASE)
    if match:
        return {
            "agent": match.group(1).lower(),
            "status": match.group(2).lower(),
            "module": match.group(3).lower()
        }
    return None


def read_test_report():
    if not os.path.exists(test_report_file):
        return None
    try:
        with open(test_report_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log(f"[Monitor] Failed to read test_report.json: {str(e)}")
        return None


def read_review_report():
    if not os.path.exists(review_report_file):
        return None
    try:
        with open(review_report_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log(f"[Monitor] Failed to read review_report.json: {str(e)}")
        return None


def get_env():
    env = os.environ.copy()
    paths = [env.get("PATH", "")]
    if sys.platform == "win32":
        npm_dir = Path.home() / "AppData" / "Roaming" / "npm"
        if npm_dir.exists():
            paths.insert(0, str(npm_dir))
        node_dir = Path("C:/Program Files/nodejs")
        if node_dir.exists():
            paths.insert(0, str(node_dir))
        env["PATH"] = ";".join([p for p in paths if p])
    else:
        env["PATH"] = ":".join([p for p in paths if p])
    return env


def get_available_models():
    """Get all available models from the current backend configuration"""
    if current_backend is None:
        return []
    return current_backend.get_available_models()


def select_model():
    """Interactive model selection"""
    global SELECTED_MODEL
    
    models = get_available_models()
    if not models:
        log("[Model] No models found in config, using default")
        return None
    
    print("\nAvailable models:")
    print("-" * 50)
    for i, m in enumerate(models, 1):
        print(f"  [{i}] {m['id']}")
    print("-" * 50)
    
    while True:
        try:
            choice = input("\nPlease select a model (enter number): ").strip()
            if not choice:
                print("Using default model")
                return None
            idx = int(choice)
            if 1 <= idx <= len(models):
                selected = models[idx - 1]
                SELECTED_MODEL = selected["id"]
                print(f"Selected: {SELECTED_MODEL}")
                return SELECTED_MODEL
            else:
                print(f"Invalid number, please enter 1-{len(models)}")
        except ValueError:
            print("Please enter a valid number")
        except KeyboardInterrupt:
            print("\nCancelled")
            sys.exit(0)


def get_opencode_path():
    """Get AI execution engine command path (compatible with old interface, delegates to backend)"""
    if current_backend is not None:
        return current_backend.get_command_path()
    from backend import OpenCodeBackend
    return OpenCodeBackend().get_command_path()


def _parse_claude_stream_json(line):
    """Parse a line of output in Claude Code stream-json format
    
    Returns (text_to_display, is_heartbeat)
    - text_to_display: extracted meaningful text (None means no display needed)
    - is_heartbeat: True indicates an event was received (for updating idle timer)
    """
    stripped = line.strip()
    if not stripped:
        return None, False
    
    try:
        event = json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        return line, True
    
    event_type = event.get("type", "")
    
    if event_type == "assistant":
        message = event.get("message", {})
        content = message.get("content", [])
        texts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                texts.append(block.get("text", ""))
        if texts:
            return "\n".join(texts) + "\n", True
        return None, True
    
    elif event_type == "result":
        result_text = event.get("result", "")
        if result_text:
            return result_text + "\n", True
        return None, True
    
    elif event_type == "tool_use":
        tool_name = event.get("tool", event.get("name", ""))
        return f"[Tool] {tool_name}\n", True
    
    elif event_type == "tool_result":
        return None, True
    
    elif event_type == "system":
        subtype = event.get("subtype", "")
        if subtype == "init":
            return None, True
        return None, True
    
    else:
        return None, True


def run_agent(agent, prompt, iteration):
    cmd = current_backend.build_run_cmd(agent, prompt, SELECTED_MODEL)
    is_claude_stream = (current_backend.name == "claude")
    
    start_time = time.time()
    output_lines = []
    process = None
    last_output_time = [time.time()]
    timeout_killed = [False]
    
    def timeout_watcher():
        warned = [False]
        while not timeout_killed[0]:
            time.sleep(10)
            if timeout_killed[0]:
                break
            idle_time = time.time() - last_output_time[0]
            if idle_time > IDLE_TIMEOUT:
                log(f"Session {iteration} IDLE TIMEOUT (no output for {IDLE_TIMEOUT}s)! Killing...")
                if process and process.pid:
                    kill_process_tree(process.pid)
                timeout_killed[0] = True
                break
            elif idle_time > IDLE_TIMEOUT - 60 and not warned[0]:
                log(f"[Warning] Session {iteration} approaching timeout ({int(idle_time)}s idle)")
                warned[0] = True
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=project_dir,
            env=get_env(),
            bufsize=0
        )
        
        watcher = threading.Thread(target=timeout_watcher, daemon=True)
        watcher.start()
        
        if process.stdout:
            for raw_line in iter(process.stdout.readline, b''):
                if timeout_killed[0]:
                    break
                if raw_line:
                    try:
                        line = raw_line.decode('utf-8', errors='replace')
                    except Exception:
                        line = raw_line.decode('latin-1', errors='replace')
                    
                    if is_claude_stream:
                        text, is_heartbeat = _parse_claude_stream_json(line)
                        if is_heartbeat:
                            last_output_time[0] = time.time()
                        if text:
                            filtered = filter_and_print(text)
                            if filtered:
                                output_lines.append(filtered)
                    else:
                        last_output_time[0] = time.time()
                        filtered = filter_and_print(line)
                        if filtered:
                            output_lines.append(filtered)
        
        if not timeout_killed[0]:
            process.wait(timeout=60)
        
        output = ''.join(output_lines)
        duration = time.time() - start_time
        
        if timeout_killed[0]:
            log(f"Session {iteration} was killed due to idle timeout.")
            return output, "timeout", duration
        else:
            log(f"Session {iteration} completed", to_file_only=True)
            return output, "success", duration
            
    except subprocess.TimeoutExpired:
        if process and process.pid:
            kill_process_tree(process.pid)
        log(f"Session {iteration} timeout!")
        return "", "timeout", time.time() - start_time
    except FileNotFoundError:
        log(f"Session {iteration} error: {current_backend.name} command not found!")
        log(current_backend.get_install_hint())
        log(f"HarnessCode cannot run without {current_backend.name}. Exiting.")
        sys.exit(1)
    except Exception as e:
        log(f"Session {iteration} error: {str(e)}")
        return "", "error", time.time() - start_time
    finally:
        timeout_killed[0] = True


orchestrator_prompt = "Follow your system instructions: read state from .harnesscode/, decide next agent, output decision in format '--- ORCHESTRATOR NEXT: [AGENT] [args] ---', exit cleanly."


def get_agent_prompt(agent, args=""):
    base_prompt = f"Read .harnesscode/claude-progress.txt and .harnesscode/feature_list.json first, follow your system instructions, complete ONE task, update progress, then exit cleanly."
    
    if args:
        return f"{base_prompt} Orchestrator instruction: {args}"
    return base_prompt


def send_im_message(message):
    webhook_url = get_webhook_url()
    if not webhook_url:
        return False
    
    try:
        body = json.dumps({"text": message}).encode('utf-8')
        req = Request(
            webhook_url,
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST"
        )
        with urlopen(req, timeout=10) as response:
            if response.status == 200:
                log("[IM] Message sent successfully", to_file_only=True)
                return True
    except (URLError, HTTPError, Exception) as e:
        log(f"[IM] Failed to send message: {str(e)}")
    return False


def normalize_feature_status(status):
    """Normalize various completion statuses that AI agents may output to completed/pending"""
    if not status:
        return "pending"
    s = status.strip().lower()
    if s in ("completed", "done", "finish", "finished", "complete", "passed"):
        return "completed"
    return s


def normalize_feature_list(data):
    """Normalize the status field of all features in feature_list"""
    if not data:
        return data
    if isinstance(data, list):
        for f in data:
            if isinstance(f, dict) and "status" in f:
                f["status"] = normalize_feature_status(f["status"])
    elif isinstance(data, dict) and "features" in data:
        for f in data["features"]:
            if isinstance(f, dict) and "status" in f:
                f["status"] = normalize_feature_status(f["status"])
    return data


def read_feature_list():
    if not os.path.exists(feature_list_file):
        return None
    try:
        with open(feature_list_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return normalize_feature_list(data)
    except Exception as e:
        log(f"[Monitor] Failed to read feature_list.json: {str(e)}")
        return None


def read_missing_info():
    if not os.path.exists(missing_info_file):
        return {"missing_items": []}
    try:
        with open(missing_info_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log(f"[Monitor] Failed to read missing_info.json: {str(e)}")
        return {"missing_items": []}


def get_progress(data):
    if not data:
        return None
    if isinstance(data, list):
        features = data
    elif isinstance(data, dict) and "features" in data:
        features = data["features"]
    else:
        return None
    total = len(features)
    passing = sum(1 for f in features if f.get("status") == "completed")
    percent = round((passing / total) * 100, 1) if total > 0 else 0
    return {"total": total, "passing": passing, "percent": percent}


def get_changes(old_data, new_data):
    if not old_data or not new_data:
        return []
    
    changes = []
    old_features = {f.get("id"): f for f in get_features_from_data(old_data)}
    
    for new_f in get_features_from_data(new_data):
        fid = new_f.get("id")
        old_f = old_features.get(fid)
        if old_f and old_f.get("status") != new_f.get("status"):
            status = "[PASS]" if new_f.get("status") == "completed" else "[FAIL]"
            name = new_f.get("name") or new_f.get("description", "")[:30]
            changes.append(f"{status} {fid}: {name}")
    
    return changes


def get_features_from_data(data):
    """Get the features list from feature_list data uniformly, supporting both dict and list formats"""
    if not data:
        return []
    if isinstance(data, list):
        return data
    return data.get("features", [])


def check_skip_possible(blocked_task_args):
    """Check if there are other pending features that can skip the current block and continue working"""
    try:
        data = read_feature_list()
        if not data:
            return {"can_skip": False}
        
        features = get_features_from_data(data)
        
        blocked_id = None
        if blocked_task_args:
            parts = blocked_task_args.strip().split()
            if len(parts) >= 2:
                try:
                    blocked_id = int(parts[-1])
                except ValueError:
                    pass
        
        for f in features:
            if f.get("status") != "pending":
                continue
            deps = f.get("dependencies", [])
            if blocked_id is None or blocked_id not in deps:
                return {
                    "can_skip": True,
                    "agent": "coder",
                    "args": f"{f.get('module', 'unknown')} {f.get('id')}",
                    "next_task": f"Feature {f.get('id')}: {f.get('description', '')[:50]}"
                }
        
        return {"can_skip": False}
    except Exception as e:
        log(f"[SkipCheck] Error: {str(e)}")
        return {"can_skip": False}


def check_missing_info_resolved():
    try:
        data = read_missing_info()
        items = data.get("missing_items", [])
        resolved = [item for item in items if item.get("status") in ["done", "skip"]]
        return resolved
    except Exception:
        return []


def check_and_notify_progress():
    global last_feature_list
    
    current_data = read_feature_list()
    if not current_data:
        return
    
    if last_feature_list is None:
        progress = get_progress(current_data)
        if progress:
            msg = f"[Monitor Started] Current: {progress['passing']}/{progress['total']} ({progress['percent']}%)"
            send_im_message(msg)
            log(f"[Monitor] Initial state: {progress['passing']}/{progress['total']} ({progress['percent']}%)")
    else:
        changes = get_changes(last_feature_list, current_data)
        if changes:
            progress = get_progress(current_data)
            if progress:
                msg = f"[Progress Update] {progress['passing']}/{progress['total']} ({progress['percent']}%)\n\nChanges:\n" + "\n".join(changes)
                send_im_message(msg)
                log(f"[Monitor] Changes detected: {len(changes)}")
    
    last_feature_list = current_data


def find_git_repos(base_dir, max_depth=2):
    """Scan base_dir and its subdirectories up to max_depth levels for Git repositories, return list of repository root directories"""
    repos = []
    base_dir = os.path.abspath(base_dir)
    
    def scan_dir(current_dir, depth):
        if depth > max_depth:
            return
        
        git_dir = os.path.join(current_dir, ".git")
        if os.path.isdir(git_dir):
            repos.append(current_dir)
            # Continue scanning subdirectories, there may be other Git repositories
        
        try:
            for entry in os.listdir(current_dir):
                entry_path = os.path.join(current_dir, entry)
                if os.path.isdir(entry_path) and entry not in (".git", "node_modules", "__pycache__", ".venv", "venv"):
                    scan_dir(entry_path, depth + 1)
        except (PermissionError, OSError):
            pass
    
    scan_dir(base_dir, 0)
    return list(set(repos))  # deduplicate


def list_branches(repo_dir):
    """List all local and remote branches of the repository, returns (local_branches, remote_branches)"""
    local_branches = []
    remote_branches = []
    
    try:
        # Local branches
        result = subprocess.run(
            ["git", "branch", "--list", "--format=%(refname:short)"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=10
        )
        if result.returncode == 0:
            local_branches = [b.strip() for b in result.stdout.splitlines() if b.strip()]
        
        # Remote branches
        result = subprocess.run(
            ["git", "branch", "-r", "--list", "--format=%(refname:short)"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=10
        )
        if result.returncode == 0:
            remote_branches = [b.strip() for b in result.stdout.splitlines() if b.strip() and "HEAD" not in b]
    except Exception as e:
        print(f"[HarnessCode] Failed to get branches: {e}")
    
    return local_branches, remote_branches


def select_branch_for_repo(repo_dir):
    """Interactively select a branch for a single Git repository, returns the selected branch name (or new branch name if newly created)"""
    print(f"\n[Git Repository] {repo_dir}")
    
    local_branches, remote_branches = list_branches(repo_dir)
    
    # Merge branch lists and remove duplicates.
    all_branches = []
    seen = set()
    for b in local_branches + remote_branches:
        if b not in seen:
            all_branches.append(b)
            seen.add(b)
    
    if not all_branches:
        print("  This repository has no branch information")
        new_branch = input("  Create new branch? Enter new branch name (leave empty to skip): ").strip()
        if new_branch:
            try:
                subprocess.run(
                    ["git", "checkout", "-b", new_branch],
                    cwd=repo_dir,
                    check=True,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace'
                )
                print(f"  Created and switched to branch '{new_branch}'")
                return new_branch
            except subprocess.CalledProcessError as e:
                print(f"  Failed to create branch: {e.stderr}")
                return None
        else:
            return None
    
    print("  Available branches:")
    for i, branch in enumerate(all_branches, 1):
        marker = " (current)" if branch in local_branches else ""
        print(f"    {i}. {branch}{marker}")
    print(f"    {len(all_branches) + 1}. Create new branch")
    
    while True:
        choice = input("  Please select a branch (enter number): ").strip()
        if not choice.isdigit():
            continue
        idx = int(choice)
        if 1 <= idx <= len(all_branches):
            selected = all_branches[idx - 1]
            # Create a local tracking branch for a remote-only branch.
            if selected in remote_branches and selected not in local_branches:
                local_name = selected.split("/", 1)[1] if "/" in selected else selected
                print(f"  Creating local branch '{local_name}' to track '{selected}'")
                try:
                    subprocess.run(
                        ["git", "checkout", "-b", local_name, selected],
                        cwd=repo_dir,
                        check=True,
                        capture_output=True,
                        text=True,
                        encoding='utf-8',
                        errors='replace'
                    )
                    return local_name
                except subprocess.CalledProcessError as e:
                    print(f"  Failed to switch branch: {e.stderr}")
                    return None
            else:
                # Switch directly for local branches.
                try:
                    subprocess.run(
                        ["git", "checkout", selected],
                        cwd=repo_dir,
                        check=True,
                        capture_output=True,
                        text=True,
                        encoding='utf-8',
                        errors='replace'
                    )
                    return selected
                except subprocess.CalledProcessError as e:
                    print(f"  Failed to switch branch: {e.stderr}")
                    return None
        elif idx == len(all_branches) + 1:
            # Create a new branch.
            new_branch = input("  Enter a new branch name: ").strip()
            if not new_branch:
                print("  Branch name cannot be empty")
                continue
            try:
                subprocess.run(
                    ["git", "checkout", "-b", new_branch],
                    cwd=repo_dir,
                    check=True,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace'
                )
                print(f"  Created and switched to branch '{new_branch}'")
                return new_branch
            except subprocess.CalledProcessError as e:
                print(f"  Failed to create branch: {e.stderr}")
                continue
        else:
            print("  Invalid selection, please try again")


def select_branches_for_git_repos():
    """Scan the project root and second-level directories for Git repos and let the user choose a branch for development."""
    project_dir = os.getcwd()
    print("\n[HarnessCode] Scanning Git repositories...")
    
    repos = find_git_repos(project_dir, max_depth=2)
    
    if not repos:
        print("  No Git repositories found")
        return
    
    print(f"  Found {len(repos)} Git repositories")
    
    # Sort by path to keep the prompt order stable.
    repos.sort()
    
    for repo in repos:
        selected_branch = select_branch_for_repo(repo)
        if selected_branch:
            print(f"  Repository {os.path.basename(repo)} will use branch: {selected_branch}")
        else:
            print(f"  Repository {os.path.basename(repo)} did not select a branch")


def init_project(backend_name=None):
    """Interactively initialize the project configuration."""
    global project_id, harnesscode_dir
    
    print("\n[HarnessCode Initialization]")
    print("Powered by HarnessCode\n")
    
    from backend import detect_backend, select_backend_interactive, get_backend
    if not backend_name:
        detected = detect_backend()
        if detected is None:
            backend_name = select_backend_interactive()
        elif detected:
            backend_name = detected
            print(f"[HarnessCode] Auto-detected AI backend: {backend_name}")
        else:
            backend_name = "opencode"
    else:
        print(f"[HarnessCode] Using specified AI backend: {backend_name}")
    
    # Select Git branches.
    select_branches_for_git_repos()
    
    auto_commit_input = input("Coder auto-commit mode (0=off, 1=on, default 1): ").strip()
    auto_commit = int(auto_commit_input) if auto_commit_input.isdigit() and auto_commit_input in ("0", "1") else 1
    
    os.makedirs(harnesscode_dir, exist_ok=True)
    project_id = get_or_create_project_id(project_dir)
    
    with open(os.path.join(harnesscode_dir, "project_id"), "w") as f:
        f.write(project_id)
    
    config_yaml = f"""# HarnessCode Configuration
project_id: {project_id}
backend: {backend_name}
auto_commit: {auto_commit}
"""
    
    config_path = get_project_config_file(project_dir)
    with open(config_path, "w", encoding="utf-8") as f:
        f.write(config_yaml)
    
    print(f"\nProject initialized: {project_id}")
    print(f"AI backend: {backend_name}")
    print(f"Auto-commit: {auto_commit}")
    print(f"Config file: {config_path}")
    print(f"Project data directory: {harnesscode_dir}")
    
    return project_id


def generate_dev_report(start_commit=None, report_type="final"):
    """Generate a development report only when actual progress exists.
    
    Args:
        start_commit: Initial commit hash.
        report_type: "final" (full summary) | "partial" (checkpoint report)
    """
    
    if not should_generate_report():
        log("[Report] No progress to report, skipping report generation")
        return None
    
    from pathlib import Path as PathlibPath
    
    report_dir = PathlibPath(harnesscode_dir) / "reports"
    report_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if report_type == "final":
        report_file = report_dir / f"dev-report-final-{timestamp}.md"
    else:
        report_file = report_dir / f"dev-report-partial-{timestamp}.md"
    
    lines = [
        f"# Development Report ({report_type.title()})",
        f"",
        f"> Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"> Project: {project_id}",
        f"> Report Type: {report_type}",
        f"",
        "---",
        "",
        "## Summary",
        "",
    ]
    
    feature_data = {"total": 0, "completed": 0, "pending": 0}
    data = read_feature_list()
    if data:
        features = get_features_from_data(data)
        feature_data["total"] = len(features)
        feature_data["completed"] = sum(1 for f in features if f.get("status") == "completed")
        feature_data["pending"] = sum(1 for f in features if f.get("status") == "pending")
    
    lines.extend([
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total Features | {feature_data['total']} |",
        f"| Completed | {feature_data['completed']} |",
        f"| Pending | {feature_data['pending']} |",
        "",
        "---",
        "",
        "## Code Statistics",
        "",
    ])
    
    if start_commit:
        result = subprocess.run(
            ["git", "diff", "--stat", start_commit],
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            cwd=project_dir
        )
        if result.returncode == 0 and result.stdout.strip():
            lines.append("```")
            lines.append(result.stdout.strip())
            lines.append("```")
        else:
            lines.append("N/A")
    else:
        lines.append("N/A (no start commit recorded)")
    
    lines.extend([
        "",
        "---",
        "",
        "## Agent Success Rates",
        "",
    ])
    
    if metrics:
        for agent in ["orchestrator", "coder", "tester", "fixer", "reviewer"]:
            rate = metrics.get_success_rate(agent)
            lines.append(f"- {agent}: {rate:.1%}")
    else:
        lines.append("N/A")
    
    lines.extend([
        "",
        "---",
        "",
        "## Development Log",
        "",
        f"See: dev-log.txt",
        f"See: .harnesscode/cycle-log.txt (detailed cycle logs)",
        "",
    ])
    
    report_file.write_text("\n".join(lines), encoding='utf-8')
    log(f"[Report] Generated: {report_file}")
    return str(report_file)


def main(backend_name=None):
    global project_id, metrics, knowledge_mgr, harnesscode_dir, log_file, current_backend
    
    if backend_name:
        current_backend = get_backend(backend_name)
    else:
        cfg_backend = get_backend_from_config(project_dir)
        current_backend = get_backend(cfg_backend)
    
    select_model()
    
    harnesscode_dir = os.path.join(project_dir, ".harnesscode")
    log_file = os.path.join(project_dir, "dev-log.txt")
    
    project_id = get_or_create_project_id(project_dir)
    metrics = Metrics(project_dir)
    knowledge_mgr = KnowledgeManager(project_dir)
    
    os.makedirs(harnesscode_dir, exist_ok=True)
    
    log("===== HarnessCode Started =====")
    log(f"Backend: {current_backend.name}")
    log(f"Project ID: {project_id}")
    log(f"Model: {SELECTED_MODEL or 'default'}")
    log(f"Config: {get_project_config_file(project_dir)}")
    log(f"Learning dir: {get_learning_dir(project_id)}")
    log(f"IDLE_TIMEOUT: {IDLE_TIMEOUT}s")
    
    start_commit = None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            cwd=project_dir, timeout=10
        )
        if result.returncode == 0:
            start_commit = result.stdout.strip()
            log(f"Start commit: {start_commit[:8]}")
    except Exception:
        pass
    
    iteration = 1
    last_decision = None
    same_decision_count = 0
    no_decision_count = 0
    MAX_NO_DECISION = 3
    
    while True:
        log(f"===== Cycle {iteration} =====")
        
        log("Calling orchestrator...")
        orch_output, orch_status, orch_duration = run_agent("orchestrator", orchestrator_prompt, f"{iteration}.orch")
        metrics.record_session("orchestrator", orch_status == "success", orch_duration)
        
        if orch_status != "success":
            log("Orchestrator failed, retrying next cycle...")
            time.sleep(random.randint(5, 15))
            iteration += 1
            continue
        
        next_agent, next_args = parse_orchestrator_decision(orch_output)
        
        current_decision = f"{next_agent}|{next_args}" if next_agent else ""
        if current_decision and current_decision == last_decision:
            same_decision_count += 1
            log(f"[Loop Detection] Same decision repeated {same_decision_count} times")
        else:
            same_decision_count = 1
            last_decision = current_decision
        
        if same_decision_count >= 3 and next_agent == "pause_for_human":
            log("[Loop Detection] Same PAUSE decision repeated 3 times...")
            
            resolved = check_missing_info_resolved()
            if resolved:
                log(f"[Loop Detection] User resolved {len(resolved)} missing_info items")
                same_decision_count = 0
            else:
                skip_result = check_skip_possible(next_args)
                if skip_result["can_skip"]:
                    log(f"[Loop Detection] Skipping to: {skip_result['next_task']}")
                    send_im_message(f"[AUTO SKIP] Continuing with: {skip_result['next_task']}")
                    next_agent = skip_result["agent"]
                    next_args = skip_result["args"]
                    same_decision_count = 0
                else:
                    log("[Loop Detection] All tasks blocked, stopping")
                    send_im_message("[STOPPED] All tasks blocked. Check .harnesscode/missing_info.json")
                    generate_dev_report(start_commit, report_type="partial")
                    break
        
        if next_agent == "complete":
            data = read_feature_list()
            if data:
                pending = [f for f in get_features_from_data(data) if f.get("status") == "pending"]
                if pending:
                    pending_ids = [f.get("id") for f in pending]
                    log(f"ORCHESTRATOR PREMATURE COMPLETE! {len(pending)} pending: {pending_ids}")
                    send_im_message(f"[FALSE COMPLETE] {len(pending)} features pending: {pending_ids[:10]}...")
                    time.sleep(random.randint(5, 15))
                    iteration += 1
                    continue
            
            test_report = read_test_report()
            if test_report and test_report.get("overall") == "fail":
                log(f"ORCHESTRATOR PREMATURE COMPLETE! test_report overall=fail")
                send_im_message("[FALSE COMPLETE] Test report shows failures")
                time.sleep(random.randint(5, 15))
                iteration += 1
                continue
            
            review_report = read_review_report()
            if review_report and review_report.get("overall") == "fail":
                log(f"ORCHESTRATOR PREMATURE COMPLETE! review_report overall=fail")
                send_im_message("[FALSE COMPLETE] Code review shows violations")
                time.sleep(random.randint(5, 15))
                iteration += 1
                continue
            
            log("PROJECT COMPLETE!")
            progress = get_progress(read_feature_list())
            if progress:
                send_im_message(f"[PROJECT COMPLETE] Final: {progress['passing']}/{progress['total']} ({progress['percent']}%)")
            generate_dev_report(start_commit, report_type="final")
            break
        
        if next_agent == "pause_for_human":
            log("ORCHESTRATOR PAUSED. Check .harnesscode/missing_info.json")
            send_im_message("[PAUSED] Check .harnesscode/missing_info.json")
            break
        
        if not next_agent:
            no_decision_count += 1
            log(f"No valid decision from orchestrator ({no_decision_count}/{MAX_NO_DECISION})")
            
            if no_decision_count >= MAX_NO_DECISION:
                log("Orchestrator stuck! Forcing initializer to reset state...")
                send_im_message("[ORCHESTRATOR STUCK] Forcing initializer to reset...")
                next_agent = "initializer"
                next_args = ""
                no_decision_count = 0
            else:
                time.sleep(random.randint(5, 15))
                iteration += 1
                continue
        else:
            no_decision_count = 0
        
        valid_agents = ["coder", "tester", "fixer", "initializer", "reviewer"]
        if next_agent not in valid_agents:
            log(f"Unknown agent '{next_agent}', defaulting to coder")
            next_agent = "coder"
        
        log(f"Executing: {next_agent} {next_args}".strip())
        
        log_cycle_detail(iteration, next_agent, next_args, 0, "started", "Agent started execution")
        
        agent_prompt = get_agent_prompt(next_agent, str(next_args) if next_args else "")
        agent_output, agent_status, agent_duration = run_agent(next_agent, agent_prompt, f"{iteration}.{next_agent}")
        
        metrics.record_session(next_agent, agent_status == "success", agent_duration)
        
        try:
            output_summary = agent_output[:500] if agent_output else "N/A"
            log_cycle_detail(iteration, next_agent, next_args, agent_duration, agent_status, output_summary)
        except Exception as e:
            log(f"[Error] Failed to write cycle log: {str(e)}")
        
        if next_agent == "fixer" and agent_status == "success":
            test_report = read_test_report()
            if test_report:
                layers = test_report.get("layers", {})
                all_issues = []
                sa = layers.get("static_analysis", {})
                for issue in sa.get("issues", []):
                    if issue.get("status") == "pending" and issue.get("suggested_fix"):
                        all_issues.append(issue["suggested_fix"])
                ut = layers.get("unit_test", {})
                for r in ut.get("results", []):
                    if r.get("status") == "fail" and r.get("suggested_fix"):
                        all_issues.append(r["suggested_fix"])
                if not all_issues:
                    for r in test_report.get("results", []):
                        if r.get("status") == "fail" and r.get("suggested_fix"):
                            all_issues.append(r["suggested_fix"])
                for sf in all_issues:
                    knowledge_mgr.save_bug_pattern(
                        sf.get("summary", ""),
                        sf.get("location", ""),
                        sf.get("action", "")
                    )
        
        agent_status_result = parse_agent_output_status(agent_output, next_agent)
        if agent_status_result:
            log(f"[Agent Status] {agent_status_result['agent']} - {agent_status_result['status']} - {agent_status_result['module']}")
        
        check_and_notify_progress()
        
        if "PROJECT COMPLETE" in agent_output.upper() or "ALL FEATURES PASSING" in agent_output.upper():
            data = read_feature_list()
            if data:
                features = get_features_from_data(data)
                pending = [f for f in features if f.get("status") == "pending"]
                if pending:
                    pending_ids = [f.get("id") for f in pending]
                    log(f"FALSE COMPLETION! {len(pending)} features pending: {pending_ids}")
                    send_im_message(f"[FALSE COMPLETION] {len(pending)} features pending")
                    time.sleep(random.randint(5, 15))
                    iteration += 1
                    continue
            
            test_report = read_test_report()
            if test_report and test_report.get("overall") == "fail":
                log("FALSE COMPLETION! test_report overall=fail")
                send_im_message("[FALSE COMPLETION] Test report shows failures")
                time.sleep(random.randint(5, 15))
                iteration += 1
                continue
            
            review_report = read_review_report()
            if review_report and review_report.get("overall") == "fail":
                log("FALSE COMPLETION! review_report overall=fail")
                send_im_message("[FALSE COMPLETION] Code review shows violations")
                time.sleep(random.randint(5, 15))
                iteration += 1
                continue
            
            log("COMPLETION SIGNAL DETECTED!")
            progress = get_progress(read_feature_list())
            if progress:
                send_im_message(f"[PROJECT COMPLETE] Final: {progress['passing']}/{progress['total']} ({progress['percent']}%)")
            generate_dev_report(start_commit, report_type="final")
            break
        
        time.sleep(random.randint(5, 15))
        iteration += 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "init":
        init_project()
    else:
        main()
