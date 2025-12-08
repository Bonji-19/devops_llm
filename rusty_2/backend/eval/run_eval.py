"""Evaluation harness for DevAgent tasks."""

import asyncio
import csv
import json
import subprocess
from pathlib import Path
from typing import Optional

import yaml

from ..dev_agent import DevAgentConfig, run_task
from .metrics import EvalResult


def load_tasks(tasks_file: Path) -> list[dict]:
    """
    Load tasks from a YAML file.
    
    Args:
        tasks_file: Path to the tasks.yaml file
        
    Returns:
        list[dict]: List of task dictionaries with id, description, repo_root, git_mcp_url
        
    Raises:
        FileNotFoundError: If tasks file doesn't exist
        yaml.YAMLError: If YAML parsing fails
    """
    if not tasks_file.exists():
        raise FileNotFoundError(f"Tasks file not found: {tasks_file}")
    
    with open(tasks_file, "r", encoding="utf-8") as f:
        tasks = yaml.safe_load(f)
    
    if not isinstance(tasks, list):
        raise ValueError("Tasks file must contain a list of tasks")
    
    return tasks


def run_command(
    command: list[str],
    cwd: Path,
    timeout: int = 300,
) -> tuple[bool, str, str]:
    """
    Run a shell command and return success status and output.
    
    Args:
        command: Command to run as a list of strings
        cwd: Working directory for the command
        timeout: Timeout in seconds
        
    Returns:
        tuple: (success: bool, stdout: str, stderr: str)
    """
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", f"Command timed out after {timeout} seconds"
    except Exception as e:
        return False, "", str(e)


def check_compile(repo_root: Path) -> tuple[bool, str]:
    """
    Check if the code compiles/runs successfully.
    
    Uses pytest with --maxfail=1 as a simple compile/run check.
    
    Args:
        repo_root: Path to repository root
        
    Returns:
        tuple: (success: bool, notes: str)
    """
    success, stdout, stderr = run_command(
        ["python", "-m", "pytest", "--maxfail=1", "--collect-only"],
        cwd=repo_root,
        timeout=60,
    )
    
    notes = ""
    if not success:
        notes = f"Compile check failed. stderr: {stderr[:500]}"
    
    return success, notes


def check_tests(repo_root: Path) -> tuple[bool, str]:
    """
    Check if the test suite passes.
    
    Args:
        repo_root: Path to repository root
        
    Returns:
        tuple: (success: bool, notes: str)
    """
    success, stdout, stderr = run_command(
        ["python", "-m", "pytest"],
        cwd=repo_root,
        timeout=300,
    )
    
    notes = ""
    if not success:
        notes = f"Tests failed. stderr: {stderr[:500]}"
    
    return success, notes


def check_static(repo_root: Path) -> tuple[bool, str]:
    """
    Run static checks (linters, SCA).
    
    Tries ruff first, then falls back to flake8 if ruff is not available.
    
    Args:
        repo_root: Path to repository root
        
    Returns:
        tuple: (success: bool, notes: str)
    """
    # Try ruff first
    success, stdout, stderr = run_command(
        ["ruff", "check", "."],
        cwd=repo_root,
        timeout=120,
    )
    
    if success:
        return True, "Static checks passed (ruff)"
    
    # If ruff failed or not available, try flake8
    success, stdout, stderr = run_command(
        ["flake8", "."],
        cwd=repo_root,
        timeout=120,
    )
    
    notes = ""
    if not success:
        notes = f"Static checks failed. stderr: {stderr[:500]}"
        # If both failed, note which ones were tried
        if "ruff" in stderr.lower() or "not found" in stderr.lower():
            notes = "ruff not available, tried flake8. " + notes
    
    return success, notes


def compute_diff_summary(repo_root: Path) -> str:
    """
    Compute a summary of changes made during task execution.
    
    Uses git diff to show what files were changed and how many lines.
    This is a simple helper to provide context in evaluation notes.
    
    Args:
        repo_root: Path to repository root
        
    Returns:
        str: Summary of changes (empty if git not available or no changes)
    """
    # Check if git is available and repo is a git repo
    success, stdout, stderr = run_command(
        ["git", "status", "--porcelain"],
        cwd=repo_root,
        timeout=10,
    )
    
    if not success:
        return ""
    
    if not stdout.strip():
        return "No changes detected"
    
    # Count changed files
    changed_files = stdout.strip().split("\n")
    file_count = len(changed_files)
    
    # Get diff stats
    success, diff_stdout, _ = run_command(
        ["git", "diff", "--stat"],
        cwd=repo_root,
        timeout=30,
    )
    
    if success and diff_stdout:
        # Extract summary from diff stat
        lines = diff_stdout.strip().split("\n")
        summary_line = lines[-1] if lines else ""
        return f"Changed {file_count} file(s). {summary_line}"
    
    return f"Changed {file_count} file(s)"


async def evaluate_task(
    task: dict,
    output_dir: Path,
    max_steps: int = 20,
) -> EvalResult:
    """
    Evaluate a single task.
    
    Runs the DevAgent, saves the conversation, and checks compilation,
    tests, and static analysis.
    
    Args:
        task: Task dictionary with id, description, repo_root, git_mcp_url
        output_dir: Directory to save conversation JSON files
        max_steps: Maximum number of agent steps
        
    Returns:
        EvalResult: Evaluation result for this task
    """
    task_id = task["id"]
    description = task["description"]
    repo_root = Path(task["repo_root"])
    git_mcp_url = task["git_mcp_url"]
    
    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Build DevAgentConfig
    config = DevAgentConfig(
        max_steps=max_steps,
        git_mcp_url=git_mcp_url,
        backend_name="gemini",
    )
    
    # Run the task
    result = await run_task(
        task_description=description,
        repo_root=str(repo_root),
        config=config,
    )
    
    # Save conversation
    chat_path = output_dir / f"{task_id}.json"
    result.conversation.save(chat_path)
    
    # Run evaluation checks
    compile_success, compile_notes = check_compile(repo_root)
    test_success, test_notes = check_tests(repo_root)
    static_success, static_notes = check_static(repo_root)
    
    # TODO: success_behaviour should ideally be manually evaluated
    # based on human judgement of whether the task was actually solved.
    # For now, we use test success as a proxy.
    behaviour_success = test_success
    
    # Compute diff summary
    diff_summary = compute_diff_summary(repo_root)
    
    # Build notes
    notes_parts = []
    if diff_summary:
        notes_parts.append(diff_summary)
    if not compile_success and compile_notes:
        notes_parts.append(f"Compile: {compile_notes}")
    if not test_success and test_notes:
        notes_parts.append(f"Tests: {test_notes}")
    if not static_success and static_notes:
        notes_parts.append(f"Static: {static_notes}")
    if result.error:
        notes_parts.append(f"Agent error: {result.error}")
    
    notes = " | ".join(notes_parts) if notes_parts else None
    
    return EvalResult(
        task_id=task_id,
        success_compile=compile_success,
        success_tests=test_success,
        success_behaviour=behaviour_success,
        success_static=static_success,
        steps=result.steps,
        notes=notes,
        chat_path=str(chat_path),
    )


def save_results_csv(results: list[EvalResult], output_path: Path) -> None:
    """
    Save evaluation results to a CSV file.
    
    Args:
        results: List of EvalResult objects
        output_path: Path to save CSV file
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "task_id",
                "success_compile",
                "success_tests",
                "success_behaviour",
                "success_static",
                "steps",
                "notes",
                "chat_path",
            ],
        )
        writer.writeheader()
        for result in results:
            writer.writerow(result.to_dict())


def save_results_json(results: list[EvalResult], output_path: Path) -> None:
    """
    Save evaluation results to a JSON file.
    
    Args:
        results: List of EvalResult objects
        output_path: Path to save JSON file
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    results_dict = [result.to_dict() for result in results]
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results_dict, f, indent=2, ensure_ascii=False)


async def run_evaluation(
    tasks_file: Path,
    output_dir: Path,
    summary_path: Optional[Path] = None,
    max_steps: int = 20,
) -> list[EvalResult]:
    """
    Run evaluation on all tasks.
    
    Args:
        tasks_file: Path to tasks.yaml file
        output_dir: Directory to save conversation JSON files
        summary_path: Optional path to save summary (if None, saves to output_dir/eval_summary.json)
        max_steps: Maximum number of agent steps per task
        
    Returns:
        list[EvalResult]: List of evaluation results
    """
    # Load tasks
    tasks = load_tasks(tasks_file)
    
    # Evaluate each task
    results = []
    for task in tasks:
        print(f"Evaluating task: {task['id']}")
        result = await evaluate_task(task, output_dir, max_steps)
        results.append(result)
        print(f"  - Compile: {result.success_compile}")
        print(f"  - Tests: {result.success_tests}")
        print(f"  - Static: {result.success_static}")
        print(f"  - Steps: {result.steps}")
    
    # Save summary
    if summary_path is None:
        summary_path = output_dir / "eval_summary.json"
    
    save_results_json(results, summary_path)
    save_results_csv(results, summary_path.with_suffix(".csv"))
    
    print(f"\nEvaluation complete. Results saved to {summary_path}")
    
    return results


async def main():
    """Main entry point for running evaluation."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run DevAgent evaluation")
    parser.add_argument(
        "--tasks",
        type=Path,
        default=Path(__file__).parent / "tasks.yaml",
        help="Path to tasks.yaml file",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).parent / "eval_chats",
        help="Directory to save conversation JSON files",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        help="Path to save summary file (default: output_dir/eval_summary.json)",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=20,
        help="Maximum number of agent steps per task",
    )
    
    args = parser.parse_args()
    
    await run_evaluation(
        tasks_file=args.tasks,
        output_dir=args.output_dir,
        summary_path=args.summary,
        max_steps=args.max_steps,
    )


if __name__ == "__main__":
    asyncio.run(main())

