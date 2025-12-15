"""
Behaviour validation for specific tasks.

This module provides task-specific validation to check if the agent
actually solved the task correctly, beyond just passing tests.
"""

from pathlib import Path
from typing import Optional, Tuple


# Task-specific validation patterns
TASK_PATTERNS = {
    "task-001": {
        "description": "UNO type annotations",
        "file": "3_uno/src/py/game.py",
        "must_contain": ["def __str__(self) -> str:"],
        "must_not_contain": ["def __str__(self) -> None:"],
        "min_occurrences": 3,  # Card, Action, PlayerState all have __str__
    },
    "task-002": {
        "description": "Hangman type annotation",
        "file": "1_hangman/src/py/game.py",
        "must_contain": ["def __str__(self) -> str:"],
        "must_not_contain": [],
        "min_occurrences": 1,
    },
    "task-005": {
        "description": "Dog get_fore_color type annotation",
        "file": "4_dog/src/py/game.py",
        "must_contain": ["def get_fore_color(color) -> str:"],
        "must_not_contain": ["def get_fore_color(color) -> Fore:"],
        "min_occurrences": 1,
    },
    "task-006": {
        "description": "Dog get_back_color type annotation",
        "file": "4_dog/src/py/game.py",
        "must_contain": ["def get_back_color(color) -> str:"],
        "must_not_contain": ["def get_back_color(color) -> Fore:"],
        "min_occurrences": 1,
    },
    "task-009": {
        "description": "Dog unused loop variable",
        "file": "4_dog/src/py/game.py",
        "must_contain": ["for _ in range(6):"],
        "must_not_contain": ["for card in range(6):"],
        "min_occurrences": 1,
    },
    "task-010": {
        "description": "Dog dead code removal",
        "file": "4_dog/src/py/game.py",
        "must_not_contain": ["#self.game_state.list_card_draw += self.game_state.list_card_discard"],
        "must_contain": [],
        "min_occurrences": 0,
    },
}


def check_behaviour_pattern(
    task_id: str,
    repo_root: Path
) -> Tuple[Optional[bool], str]:
    """
    Check if the task was solved correctly using pattern matching.

    This provides a semi-automated way to verify that the agent actually
    fixed the bug, beyond just passing tests.

    Args:
        task_id: The task identifier (e.g., "task-001")
        repo_root: Repository root directory

    Returns:
        Tuple of (success: Optional[bool], notes: str)
        - success is None if no pattern defined for this task
        - success is True/False if pattern check passed/failed
    """
    if task_id not in TASK_PATTERNS:
        return None, "No behaviour pattern defined for this task"

    pattern = TASK_PATTERNS[task_id]
    file_path = repo_root / pattern["file"]

    if not file_path.exists():
        return False, f"File not found: {pattern['file']}"

    try:
        content = file_path.read_text()
    except Exception as e:
        return False, f"Error reading file: {str(e)}"

    # Check must_not_contain patterns (old bug still present?)
    for bad_pattern in pattern["must_not_contain"]:
        if bad_pattern in content:
            return False, f"Bug not fixed: '{bad_pattern}' still present"

    # Check must_contain patterns (fix applied?)
    found_count = 0
    for good_pattern in pattern["must_contain"]:
        count = content.count(good_pattern)
        found_count += count

    min_required = pattern["min_occurrences"]
    if found_count < min_required:
        return False, f"Expected fix found {found_count} times, needed {min_required}"

    return True, f"Behaviour verified: {pattern['description']} fixed correctly"


def check_behaviour_diff(task_id: str, repo_root: Path) -> Tuple[Optional[bool], str]:
    """
    Check behaviour by analyzing git diff.

    Args:
        task_id: The task identifier
        repo_root: Repository root directory

    Returns:
        Tuple of (success: Optional[bool], notes: str)
    """
    import subprocess

    try:
        result = subprocess.run(
            ["git", "diff", "--stat"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return None, "Could not get git diff"

        if not result.stdout.strip():
            return False, "No changes detected"

        # Count files changed
        lines = result.stdout.strip().split("\n")
        if lines:
            summary = lines[-1]  # Last line has summary
            return True, f"Changes detected: {summary}"

        return None, "Could not parse diff"

    except subprocess.TimeoutExpired:
        return None, "Git diff timed out"
    except Exception as e:
        return None, f"Error checking diff: {str(e)}"


def check_behaviour(task_id: str, repo_root: Path) -> Tuple[Optional[bool], str]:
    """
    Main behaviour check function.

    Tries pattern matching first, falls back to diff analysis.

    Args:
        task_id: The task identifier
        repo_root: Repository root directory

    Returns:
        Tuple of (success: Optional[bool], notes: str)
    """
    # Try pattern matching first
    pattern_success, pattern_notes = check_behaviour_pattern(task_id, repo_root)

    if pattern_success is not None:
        return pattern_success, pattern_notes

    # Fall back to diff analysis
    return check_behaviour_diff(task_id, repo_root)
