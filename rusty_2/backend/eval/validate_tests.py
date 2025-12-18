"""
Validation utilities for agent-written tests.

This module provides functions to validate test code quality and effectiveness
according to the criteria outlined in TEST_VALIDATION_STRATEGY.md
"""

import subprocess
from pathlib import Path
from typing import Tuple


def run_command(cmd: list[str], cwd: Path, timeout: int = 60) -> Tuple[bool, str, str]:
    """
    Run a shell command and return success status and output.

    Args:
        cmd: Command and arguments as list
        cwd: Working directory
        timeout: Timeout in seconds

    Returns:
        Tuple of (success: bool, stdout: str, stderr: str)
    """
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except FileNotFoundError:
        return False, "", f"Command not found: {cmd[0]}"
    except Exception as e:
        return False, "", str(e)


def validate_test_lint(test_file: Path, repo_root: Path) -> Tuple[bool, str]:
    """
    Check if test file passes linting.

    Validation Criterion 1: Code Quality (Linters & Static Checks)

    Args:
        test_file: Path to test file
        repo_root: Repository root directory

    Returns:
        Tuple of (success: bool, notes: str)
    """
    # Try ruff first
    success, stdout, stderr = run_command(
        ["ruff", "check", str(test_file.relative_to(repo_root))],
        cwd=repo_root,
        timeout=30,
    )

    if success:
        return True, "Linting passed (ruff)"

    # If ruff not available, try flake8
    success_flake8, stdout_flake8, stderr_flake8 = run_command(
        ["flake8", str(test_file.relative_to(repo_root))],
        cwd=repo_root,
        timeout=30,
    )

    if success_flake8:
        return True, "Linting passed (flake8)"

    # Both failed
    error_msg = stderr if stderr else stderr_flake8
    return False, f"Linting failed: {error_msg[:200]}"


def validate_test_collection(test_file: Path, repo_root: Path) -> Tuple[bool, str, int]:
    """
    Check if pytest can collect the tests.

    Validation Criterion 2a: Syntax & Execution - Collection

    Args:
        test_file: Path to test file
        repo_root: Repository root directory

    Returns:
        Tuple of (success: bool, notes: str, test_count: int)
    """
    success, stdout, stderr = run_command(
        ["python", "-m", "pytest", str(test_file.relative_to(repo_root)), "--collect-only", "-q"],
        cwd=repo_root,
        timeout=30,
    )

    # Count tests
    test_count = 0
    if stdout:
        # Look for lines like "test_something.py::TestClass::test_method"
        for line in stdout.split("\n"):
            if "::test_" in line or line.strip().startswith("test_"):
                test_count += 1

    if not success:
        return False, f"Test collection failed: {stderr[:200]}", 0

    if test_count == 0:
        return False, "No tests collected", 0

    return True, f"Collected {test_count} test(s)", test_count


def validate_test_execution(test_file: Path, repo_root: Path) -> Tuple[bool, str, dict]:
    """
    Check if tests execute without crashes.

    Validation Criterion 2a: Syntax & Execution - Execution

    Args:
        test_file: Path to test file
        repo_root: Repository root directory

    Returns:
        Tuple of (success: bool, notes: str, stats: dict)
    """
    success, stdout, stderr = run_command(
        ["python", "-m", "pytest", str(test_file.relative_to(repo_root)), "-v"],
        cwd=repo_root,
        timeout=60,
    )

    # Parse pytest output for statistics
    stats = {
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
    }

    if stdout:
        # Look for summary line like "5 passed, 2 failed in 1.23s"
        for line in stdout.split("\n"):
            if " passed" in line or " failed" in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == "passed" and i > 0:
                        try:
                            stats["passed"] = int(parts[i-1])
                        except (ValueError, IndexError):
                            pass
                    elif part == "failed" and i > 0:
                        try:
                            stats["failed"] = int(parts[i-1])
                        except (ValueError, IndexError):
                            pass
                    elif part in ["error", "errors"] and i > 0:
                        try:
                            stats["errors"] = int(parts[i-1])
                        except (ValueError, IndexError):
                            pass

    # Check for crashes (errors during collection or execution)
    if "ERRORS" in stderr or "ERROR" in stdout:
        return False, f"Test execution crashed: {stderr[:200]}", stats

    # Success if tests ran (even if some failed)
    total_tests = stats["passed"] + stats["failed"] + stats["errors"]
    if total_tests == 0:
        return False, "No tests executed", stats

    notes = f"Executed {total_tests} test(s): {stats['passed']} passed, {stats['failed']} failed, {stats['errors']} errors"
    return True, notes, stats


def validate_test_quality(test_file: Path, repo_root: Path) -> Tuple[bool, str]:
    """
    Comprehensive test validation combining all criteria.

    This is the main validation function that should be called from run_eval.py

    Args:
        test_file: Path to test file
        repo_root: Repository root directory

    Returns:
        Tuple of (success: bool, notes: str)
    """
    notes_parts = []

    # Check 1: Linting
    lint_success, lint_notes = validate_test_lint(test_file, repo_root)
    notes_parts.append(f"Lint: {lint_notes}")

    # Check 2: Collection
    collect_success, collect_notes, test_count = validate_test_collection(test_file, repo_root)
    notes_parts.append(f"Collection: {collect_notes}")

    # Check 3: Execution (only if collection succeeded)
    if collect_success:
        exec_success, exec_notes, stats = validate_test_execution(test_file, repo_root)
        notes_parts.append(f"Execution: {exec_notes}")
    else:
        exec_success = False

    # Overall success: linting + collection + execution without crashes
    overall_success = lint_success and collect_success and exec_success

    return overall_success, " | ".join(notes_parts)


if __name__ == "__main__":
    # Example usage
    import sys

    if len(sys.argv) < 3:
        print("Usage: python validate_tests.py <test_file> <repo_root>")
        sys.exit(1)

    test_file = Path(sys.argv[1])
    repo_root = Path(sys.argv[2])

    success, notes = validate_test_quality(test_file, repo_root)

    print(f"Validation {'PASSED' if success else 'FAILED'}")
    print(f"Notes: {notes}")

    sys.exit(0 if success else 1)
