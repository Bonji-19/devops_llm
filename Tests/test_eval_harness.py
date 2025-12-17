"""Unit tests for the evaluation harness (run_eval.py).

These tests verify the evaluation infrastructure works correctly
before running it against external repositories.

Note: We import directly from the modules to avoid triggering
the full __init__.py import chain (which requires mcp, etc.)
"""

import csv
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

# Direct imports to avoid __init__.py chain that requires mcp
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the specific modules directly
from rusty_2.backend.eval.metrics import EvalResult
from rusty_2.backend.eval import run_eval

# Get functions from module
load_tasks = run_eval.load_tasks
run_command = run_eval.run_command
check_compile = run_eval.check_compile
check_tests = run_eval.check_tests
check_static = run_eval.check_static
compute_diff_summary = run_eval.compute_diff_summary
save_results_json = run_eval.save_results_json
save_results_csv = run_eval.save_results_csv


# =============================================================================
# Tests for load_tasks()
# =============================================================================

class TestLoadTasks:
    """Tests for YAML task loading."""

    def test_file_not_found(self, tmp_path: Path):
        """Should raise FileNotFoundError when tasks file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            load_tasks(tmp_path / "missing.yaml")

    def test_not_a_list(self, tmp_path: Path):
        """Should raise ValueError when YAML content is not a list."""
        tasks_file = tmp_path / "tasks.yaml"
        tasks_file.write_text(
            yaml.safe_dump({"id": "t1", "description": "not a list"}),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="must contain a list"):
            load_tasks(tasks_file)

    def test_valid_tasks(self, tmp_path: Path):
        """Should correctly load valid tasks from YAML."""
        tasks_file = tmp_path / "tasks.yaml"
        data = [
            {
                "id": "task-001",
                "description": "Fix the login bug",
                "repo_root": "/path/to/repo",
                "git_mcp_url": "stdio://python:-m:mcp_server_git",
            },
            {
                "id": "task-002",
                "description": "Add validation",
                "repo_root": "/path/to/repo2",
                "git_mcp_url": "stdio://python:-m:mcp_server_git",
            },
        ]
        tasks_file.write_text(yaml.safe_dump(data), encoding="utf-8")

        tasks = load_tasks(tasks_file)

        assert isinstance(tasks, list)
        assert len(tasks) == 2
        assert tasks[0]["id"] == "task-001"
        assert tasks[1]["description"] == "Add validation"

    def test_empty_list(self, tmp_path: Path):
        """Should handle empty task list."""
        tasks_file = tmp_path / "tasks.yaml"
        tasks_file.write_text(yaml.safe_dump([]), encoding="utf-8")

        tasks = load_tasks(tasks_file)

        assert tasks == []


# =============================================================================
# Tests for run_command()
# =============================================================================

class TestRunCommand:
    """Tests for shell command execution."""

    def test_success(self, monkeypatch, tmp_path: Path):
        """Should return success when command exits with code 0."""
        def fake_run(*args, **kwargs):
            return SimpleNamespace(returncode=0, stdout="output", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)

        success, stdout, stderr = run_command(["echo", "hi"], cwd=tmp_path)

        assert success is True
        assert stdout == "output"
        assert stderr == ""

    def test_failure(self, monkeypatch, tmp_path: Path):
        """Should return failure when command exits with non-zero code."""
        def fake_run(*args, **kwargs):
            return SimpleNamespace(returncode=1, stdout="", stderr="error message")

        monkeypatch.setattr(subprocess, "run", fake_run)

        success, stdout, stderr = run_command(["false"], cwd=tmp_path)

        assert success is False
        assert stderr == "error message"

    def test_timeout(self, monkeypatch, tmp_path: Path):
        """Should handle command timeout gracefully."""
        def fake_run(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="sleep", timeout=1)

        monkeypatch.setattr(subprocess, "run", fake_run)

        success, stdout, stderr = run_command(["sleep", "100"], cwd=tmp_path, timeout=1)

        assert success is False
        assert stdout == ""
        assert "timed out" in stderr.lower()

    def test_exception(self, monkeypatch, tmp_path: Path):
        """Should handle unexpected exceptions."""
        def fake_run(*args, **kwargs):
            raise OSError("Command not found")

        monkeypatch.setattr(subprocess, "run", fake_run)

        success, stdout, stderr = run_command(["nonexistent"], cwd=tmp_path)

        assert success is False
        assert "Command not found" in stderr


# =============================================================================
# Tests for check_compile()
# =============================================================================

class TestCheckCompile:
    """Tests for compilation/syntax checking."""

    def test_compile_success(self, monkeypatch, tmp_path: Path):
        """Should return success when py_compile succeeds on all files."""
        # Create a test Python file
        test_file = tmp_path / "src" / "test.py"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("print('hello')")

        monkeypatch.setattr(
            "rusty_2.backend.eval.run_eval.run_command",
            lambda *a, **k: (True, "", ""),
        )

        success, notes = check_compile(tmp_path)

        assert success is True
        assert notes == ""

    def test_compile_no_files(self, monkeypatch, tmp_path: Path):
        """Should return success with note when no Python files found."""
        success, notes = check_compile(tmp_path)

        assert success is True
        assert "No Python files found" in notes

    def test_compile_failure(self, monkeypatch, tmp_path: Path):
        """Should return failure with notes when compilation fails."""
        # Create a test Python file
        test_file = tmp_path / "src" / "test.py"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("print('hello')")

        monkeypatch.setattr(
            "rusty_2.backend.eval.run_eval.run_command",
            lambda *a, **k: (False, "", "SyntaxError: invalid syntax"),
        )

        success, notes = check_compile(tmp_path)

        assert success is False
        assert "Compile errors" in notes
        assert "SyntaxError" in notes

    def test_compile_truncates_long_stderr(self, monkeypatch, tmp_path: Path):
        """Should truncate very long error messages."""
        # Create a test Python file
        test_file = tmp_path / "src" / "test.py"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("print('hello')")

        long_error = "E" * 1000
        monkeypatch.setattr(
            "rusty_2.backend.eval.run_eval.run_command",
            lambda *a, **k: (False, "", long_error),
        )

        success, notes = check_compile(tmp_path)

        assert success is False
        assert len(notes) < len(long_error)  # Should be truncated


# =============================================================================
# Tests for check_tests()
# =============================================================================

class TestCheckTests:
    """Tests for test suite execution."""

    def test_tests_pass(self, monkeypatch, tmp_path: Path):
        """Should return success when all tests pass."""
        monkeypatch.setattr(
            "rusty_2.backend.eval.run_eval.run_command",
            lambda *a, **k: (True, "5 passed", ""),
        )

        success, notes = check_tests(tmp_path)

        assert success is True
        assert notes == ""

    def test_tests_fail(self, monkeypatch, tmp_path: Path):
        """Should return failure when tests fail."""
        call_count = {"n": 0}

        def fake_run_command(cmd, cwd, timeout=0):
            call_count["n"] += 1
            if call_count["n"] == 1:
                # First call: pytest --collect-only (succeeds, finds tests)
                return True, "collected 5 items", ""
            else:
                # Second call: pytest (test execution fails)
                return False, "", "FAILED test_foo.py::test_bar"

        monkeypatch.setattr(
            "rusty_2.backend.eval.run_eval.run_command",
            fake_run_command,
        )

        success, notes = check_tests(tmp_path)

        assert success is False
        assert "Tests failed" in notes or "FAILED" in notes


# =============================================================================
# Tests for check_static()
# =============================================================================

class TestCheckStatic:
    """Tests for static analysis (ruff/flake8)."""

    def test_ruff_passes(self, monkeypatch, tmp_path: Path):
        """Should return success when ruff passes."""
        monkeypatch.setattr(
            "rusty_2.backend.eval.run_eval.run_command",
            lambda *a, **k: (True, "", ""),
        )

        success, notes = check_static(tmp_path)

        assert success is True
        assert "ruff" in notes.lower()

    def test_ruff_fails_flake8_passes(self, monkeypatch, tmp_path: Path):
        """Should fall back to flake8 when ruff is not available."""
        import sys
        from pathlib import Path as P

        # Mock Path.exists to make ruff_path not exist
        original_exists = P.exists
        def fake_exists(self):
            if "ruff" in str(self):
                return False
            return original_exists(self)

        monkeypatch.setattr(P, "exists", fake_exists)

        # Mock shutil.which to return None for ruff
        monkeypatch.setattr("shutil.which", lambda x: None if x == "ruff" else "/bin/flake8")

        # Create src directory so check_path logic works
        (tmp_path / "src").mkdir()

        # Mock run_command to simulate flake8 passing
        monkeypatch.setattr(
            "rusty_2.backend.eval.run_eval.run_command",
            lambda *a, **k: (True, "", ""),
        )

        success, notes = check_static(tmp_path)

        assert success is True
        assert "flake8" in notes.lower()

    def test_both_fail(self, monkeypatch, tmp_path: Path):
        """Should return failure when both ruff and flake8 fail."""
        monkeypatch.setattr(
            "rusty_2.backend.eval.run_eval.run_command",
            lambda *a, **k: (False, "", "linter error"),
        )

        success, notes = check_static(tmp_path)

        assert success is False
        assert "Static checks failed" in notes


# =============================================================================
# Tests for compute_diff_summary()
# =============================================================================

class TestComputeDiffSummary:
    """Tests for git diff summary computation."""

    def test_not_a_git_repo(self, monkeypatch, tmp_path: Path):
        """Should return empty string if not a git repo."""
        monkeypatch.setattr(
            "rusty_2.backend.eval.run_eval.run_command",
            lambda *a, **k: (False, "", "not a git repository"),
        )

        result = compute_diff_summary(tmp_path)

        assert result == ""

    def test_no_changes(self, monkeypatch, tmp_path: Path):
        """Should indicate no changes when working tree is clean."""
        monkeypatch.setattr(
            "rusty_2.backend.eval.run_eval.run_command",
            lambda *a, **k: (True, "", ""),  # Empty stdout = no changes
        )

        result = compute_diff_summary(tmp_path)

        assert result == "No changes detected"

    def test_with_changes(self, monkeypatch, tmp_path: Path):
        """Should summarize changes when files are modified."""
        call_count = {"n": 0}

        def fake_run_command(cmd, cwd, timeout=0):
            call_count["n"] += 1
            if call_count["n"] == 1:
                # git status --porcelain
                return True, " M file1.py\n M file2.py\n", ""
            else:
                # git diff --stat
                return True, "file1.py | 5 ++---\nfile2.py | 2 +-\n2 files changed", ""

        monkeypatch.setattr(
            "rusty_2.backend.eval.run_eval.run_command",
            fake_run_command,
        )

        result = compute_diff_summary(tmp_path)

        assert "2" in result  # 2 files changed


# =============================================================================
# Tests for save_results_json()
# =============================================================================

class TestSaveResultsJson:
    """Tests for JSON result saving."""

    def test_save_single_result(self, tmp_path: Path):
        """Should save a single result to JSON."""
        result = EvalResult(
            task_id="task-001",
            success_compile=True,
            success_tests=True,
            success_behaviour=True,
            success_static=False,
            steps=5,
            notes="Some notes",
            chat_path="chat.json",
        )
        output_path = tmp_path / "results.json"

        save_results_json([result], output_path)

        assert output_path.exists()
        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert len(data) == 1
        assert data[0]["task_id"] == "task-001"
        assert data[0]["success_compile"] is True
        assert data[0]["success_static"] is False
        assert data[0]["steps"] == 5

    def test_save_multiple_results(self, tmp_path: Path):
        """Should save multiple results to JSON."""
        results = [
            EvalResult("t1", True, True, True, True, 3),
            EvalResult("t2", False, False, False, False, 10, notes="Failed"),
        ]
        output_path = tmp_path / "results.json"

        save_results_json(results, output_path)

        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert len(data) == 2
        assert data[0]["task_id"] == "t1"
        assert data[1]["task_id"] == "t2"
        assert data[1]["notes"] == "Failed"

    def test_creates_parent_directories(self, tmp_path: Path):
        """Should create parent directories if they don't exist."""
        output_path = tmp_path / "nested" / "dir" / "results.json"
        result = EvalResult("t1", True, True, True, True, 1)

        save_results_json([result], output_path)

        assert output_path.exists()


# =============================================================================
# Tests for save_results_csv()
# =============================================================================

class TestSaveResultsCsv:
    """Tests for CSV result saving."""

    def test_save_single_result(self, tmp_path: Path):
        """Should save a single result to CSV."""
        result = EvalResult(
            task_id="task-001",
            success_compile=True,
            success_tests=False,
            success_behaviour=False,
            success_static=True,
            steps=7,
        )
        output_path = tmp_path / "results.csv"

        save_results_csv([result], output_path)

        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        rows = list(csv.DictReader(content.splitlines()))
        assert len(rows) == 1
        assert rows[0]["task_id"] == "task-001"
        assert rows[0]["success_compile"] == "True"
        assert rows[0]["success_tests"] == "False"
        assert rows[0]["steps"] == "7"

    def test_csv_has_correct_headers(self, tmp_path: Path):
        """Should have all expected column headers."""
        result = EvalResult("t1", True, True, True, True, 1)
        output_path = tmp_path / "results.csv"

        save_results_csv([result], output_path)

        content = output_path.read_text(encoding="utf-8")
        header_line = content.splitlines()[0]
        expected_headers = [
            "task_id",
            "success_compile",
            "success_tests",
            "success_behaviour",
            "success_static",
            "steps",
            "notes",
            "chat_path",
        ]
        for header in expected_headers:
            assert header in header_line


# =============================================================================
# Tests for EvalResult
# =============================================================================

class TestEvalResult:
    """Tests for EvalResult dataclass."""

    def test_to_dict(self):
        """Should convert to dictionary correctly."""
        result = EvalResult(
            task_id="t1",
            success_compile=True,
            success_tests=False,
            success_behaviour=False,
            success_static=True,
            steps=5,
            notes="Test notes",
            chat_path="/path/to/chat.json",
        )

        d = result.to_dict()

        assert d["task_id"] == "t1"
        assert d["success_compile"] is True
        assert d["success_tests"] is False
        assert d["steps"] == 5
        assert d["notes"] == "Test notes"

    def test_from_dict(self):
        """Should create from dictionary correctly."""
        data = {
            "task_id": "t2",
            "success_compile": False,
            "success_tests": True,
            "success_behaviour": True,
            "success_static": False,
            "steps": 12,
            "notes": None,
            "chat_path": None,
        }

        result = EvalResult.from_dict(data)

        assert result.task_id == "t2"
        assert result.success_compile is False
        assert result.success_tests is True
        assert result.steps == 12

    def test_roundtrip(self):
        """Should survive to_dict -> from_dict roundtrip."""
        original = EvalResult("t1", True, False, False, True, 3, "notes", "path.json")

        restored = EvalResult.from_dict(original.to_dict())

        assert restored.task_id == original.task_id
        assert restored.success_compile == original.success_compile
        assert restored.success_tests == original.success_tests
        assert restored.steps == original.steps
        assert restored.notes == original.notes