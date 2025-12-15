# Test Validation Strategy for Agent-Written Tests

## Overview
When the DevAgent writes its own unit tests, we need to validate both the **code quality** and **test effectiveness**. This document outlines the validation criteria based on team feedback.

## Validation Dimensions

### 1. Code Quality (Linters & Static Checks)
**Question:** Does the test code pass linting and static checks?

**How to validate:**
- Run `ruff check` or `flake8` on the test file
- Check for common issues:
  - Unused imports
  - Undefined variables
  - Code style violations (PEP 8)
  - Type annotation errors
  - Complexity issues

**Success criteria:**
- ✅ No linting errors
- ✅ No undefined names
- ✅ Follows project code style

### 2. Test Correctness (Functionality)
**Question:** Does it test the right things with the right code?

**How to validate:**

#### 2a. Syntax & Execution
- Does the test file import correctly?
- Do the tests run without syntax errors?
- Can pytest collect and execute the tests?

**Success criteria:**
- ✅ `pytest --collect-only` succeeds
- ✅ Tests execute without exceptions (pass or fail is okay, crashes are not)

#### 2b. Test Coverage
- Does the test cover the intended functionality?
- Are edge cases tested?
- Are both positive and negative cases covered?

**Manual inspection criteria:**
- ✅ Tests the correct function/class
- ✅ Uses appropriate assertions
- ✅ Tests meaningful scenarios (not just trivial cases)
- ✅ Includes edge cases where appropriate

#### 2c. Test Quality
- Are test names descriptive?
- Are fixtures used appropriately?
- Is test data realistic?
- Are assertions specific and meaningful?

**Quality checklist:**
- ✅ Descriptive test function names (e.g., `test_card_color_is_red`)
- ✅ Proper use of pytest fixtures
- ✅ Realistic test data (not just `foo`, `bar`, `test`)
- ✅ Specific assertions (`assert x == 5`, not just `assert x`)

#### 2d. Test Effectiveness
- Do the tests actually detect bugs?
- Would they fail if the implementation is broken?

**Mutation testing approach:**
- Introduce a bug in the implementation
- Run the test - it should fail
- If test still passes, the test is ineffective

**Success criteria:**
- ✅ Test fails when implementation is intentionally broken
- ✅ Test passes when implementation is correct

## Validation Workflow

### For Each Test-Writing Task:

1. **Run the agent** to generate tests
2. **Lint check:** Run static checks on generated test file
3. **Syntax check:** Run `pytest --collect-only`
4. **Execution check:** Run `pytest` on the test file
5. **Manual review:** Check test quality and coverage
6. **Mutation test (optional):** Introduce bugs and verify tests catch them

## Proposed Test-Writing Tasks

### Easy Test-Writing Tasks:
1. **Write unit test for Card.__str__()** (3_uno/src/py/game.py:28)
   - Test with different colors and symbols
   - Verify colorama formatting

2. **Write unit test for get_fore_color()** (4_dog/src/py/game.py:10)
   - Test all color mappings
   - Test None handling

### Medium Test-Writing Tasks:
3. **Write integration test for Hangman game flow**
   - Test full game from setup to completion
   - Test win and lose scenarios

4. **Write unit tests for Battleship ship placement**
   - Test valid placements
   - Test invalid placements (out of bounds, overlapping)

## Automated Validation Script

We should extend `run_eval.py` with a new check function:

```python
def validate_test_quality(test_file_path: Path, implementation_file: Path) -> tuple[bool, str]:
    """
    Validate agent-written tests.

    Checks:
    1. Linting passes
    2. Tests can be collected
    3. Tests execute without crashes
    4. (Optional) Manual quality score

    Returns:
        tuple: (success: bool, notes: str)
    """
    # Check 1: Lint the test file
    lint_success, _ = run_command(["ruff", "check", str(test_file_path)])

    # Check 2: Collect tests
    collect_success, stdout, _ = run_command(
        ["pytest", str(test_file_path), "--collect-only"]
    )

    # Check 3: Execute tests
    exec_success, _, stderr = run_command(
        ["pytest", str(test_file_path), "-v"]
    )

    # Build notes
    notes_parts = []
    if not lint_success:
        notes_parts.append("Linting failed")
    if not collect_success:
        notes_parts.append("Test collection failed")
    if not exec_success:
        notes_parts.append("Test execution crashed")

    # Manual quality metrics would be added here
    # For now, automated checks only

    success = lint_success and collect_success
    return success, " | ".join(notes_parts) if notes_parts else "Tests validated"
```

## Example Evaluation Output

For a test-writing task, the evaluation summary would include:

```json
{
  "task_id": "task-013-write-card-test",
  "success_lint": true,
  "success_collect": true,
  "success_execute": true,
  "test_count": 5,
  "coverage": "manual review pending",
  "notes": "Generated 5 tests for Card.__str__(). All tests pass linting and execute successfully.",
  "quality_score": "TBD (manual review)"
}
```

## Team Feedback Integration

This strategy directly addresses Silvan's feedback:

> "wenn er selber tests schribt, lueg demfall ob de linter funktioniert & öbs richtige tested wird mitem richtige code"

Translation: "If it writes tests itself, check if the linter works & if it tests the right things with the right code"

✅ **Linter check:** Automated via ruff/flake8
✅ **Right things, right code:** Manual review + mutation testing

## Next Steps

1. Add 2-3 test-writing tasks to tasks.yaml
2. Extend run_eval.py with validate_test_quality()
3. Run evaluation on test-writing tasks
4. Manually review generated tests for quality
5. Document findings for Friday demo
