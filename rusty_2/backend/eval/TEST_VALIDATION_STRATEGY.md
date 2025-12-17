# Test Validation Strategy for Agent-Written Tests

## Overview
When the DevAgent writes unit tests autonomously, validating both **code quality** and **test effectiveness** is critical. This document outlines the validation strategy implemented in the evaluation framework to ensure agent-generated tests meet professional standards.

## Validation Dimensions

### 1. Code Quality (Static Analysis)
**Question:** Does the test code pass linting and static checks?

**Implementation:**
- Run `ruff check` or `flake8` on the test file
- Integrated into the standard evaluation pipeline via `check_static()`

**Checks performed:**
- Unused imports
- Undefined variables
- Code style violations (PEP 8)
- Type annotation errors
- Complexity issues

**Success criteria:**
- ✅ No linting errors
- ✅ No undefined names
- ✅ Follows project code style

### 2. Test Collection & Syntax
**Question:** Can pytest discover and parse the test file without errors?

**Implementation:**
- Run `pytest --collect-only` on the test file
- Validates syntax, imports, and test structure
- Integrated into `check_tests()` function

**Success criteria:**
- ✅ Test file imports successfully
- ✅ Pytest can collect test functions
- ✅ No syntax errors or import failures

### 3. Test Execution
**Question:** Do the tests execute without crashing?

**Implementation:**
- Run `pytest` on the test file
- Tests may pass or fail, but should not crash
- Failures indicate test logic issues, crashes indicate structural problems

**Success criteria:**
- ✅ Tests execute without exceptions
- ✅ No collection errors
- ✅ Tests produce assertions (pass/fail counts)

### 4. Test Coverage & Correctness
**Question:** Does the test cover the intended functionality?

**Validation approach:**
- Pattern matching in `behaviour_checks.py` to verify:
  - Presence of test functions (`def test_`)
  - References to the target function being tested
  - Appropriate assertion count

**Manual inspection criteria:**
- ✅ Tests the correct function/class
- ✅ Uses appropriate assertions
- ✅ Tests meaningful scenarios (not just trivial cases)
- ✅ Includes edge cases where appropriate

### 5. Test Effectiveness (Optional)
**Question:** Would the tests detect bugs if the implementation breaks?

**Mutation testing approach:**
- Introduce a bug in the implementation
- Run the test suite - it should fail
- If tests still pass, they are ineffective

**Success criteria:**
- ✅ Test fails when implementation is intentionally broken
- ✅ Test passes when implementation is correct

## Implemented Validation Workflow

### Automated Validation (Integrated into `run_eval.py`)

For each test-writing task, the evaluation harness performs:

1. **Compilation Check** (`check_compile()`)
   - Uses `py_compile` to validate Python syntax
   - Ensures test file has no syntax errors

2. **Test Collection** (`check_tests()`)
   - Runs `pytest --collect-only`
   - Verifies pytest can discover and parse tests

3. **Test Execution** (`check_tests()`)
   - Runs `pytest` on the test suite
   - Validates tests execute without crashes

4. **Static Analysis** (`check_static()`)
   - Runs `ruff check` (fallback to `flake8`)
   - Ensures code quality standards

5. **Behavior Validation** (`check_behaviour()`)
   - Pattern matching to verify test presence
   - Confirms correct function is being tested

### Behavior Validation Example

For task-009 (write tests for `get_fore_color()`):

```python
"task-009": {
    "description": "Dog test writing for get_fore_color",
    "file": "4_dog/tests/test_game.py",
    "must_contain": ["def test_", "get_fore_color"],
    "must_not_contain": [],
    "min_occurrences": 2,
}
```

This validates:
- At least 2 occurrences of required patterns
- Test function exists (`def test_`)
- Target function is referenced (`get_fore_color`)

## Validation Results Format

For a test-writing task, the evaluation output includes:

```json
{
  "task_id": "task-009",
  "success_compile": true,
  "success_tests": true,
  "success_behaviour": true,
  "success_static": true,
  "steps": 9,
  "notes": "Changed 1 file(s) | Behaviour: Dog test writing for get_fore_color fixed correctly",
  "chat_path": "rusty_2/backend/eval/eval_chats/task-009.json"
}
```

All four success criteria must pass for the task to be considered successful.

## Test-Writing Tasks in Evaluation Suite

### Current Implementation

**Task 009: Write Unit Tests for get_fore_color()**
- **Difficulty:** Easy (Test Writing)
- **Target:** `4_dog/src/py/game.py:10`
- **Requirements:**
  - Test all color mappings (red, green, yellow, blue)
  - Test None handling
  - Test invalid colors
  - Each test verifies correct Fore constant is returned

**Validation Strategy:**
1. ✅ Lint check: Test code passes ruff/flake8
2. ✅ Collection: Pytest can discover tests
3. ✅ Execution: Tests run without errors
4. ✅ Behavior: Pattern matching confirms test presence and target function reference

## Quality Metrics

### Automated Metrics (Implemented)
- **Linter pass rate:** Percentage of tasks where static checks pass
- **Collection success:** Percentage of tasks where pytest can collect tests
- **Execution success:** Percentage of tasks where tests execute
- **Behavior match:** Percentage of tasks where pattern validation succeeds

### Manual Quality Metrics (Future Enhancement)
- Test name descriptiveness
- Assertion specificity
- Edge case coverage
- Fixture usage appropriateness

## Integration with Evaluation Pipeline

The test validation strategy is fully integrated into `run_eval.py`:

```python
# For all tasks (including test-writing tasks)
success_compile, _ = check_compile(repo_root)
success_tests, _ = check_tests(repo_root)
success_static, _ = check_static(repo_root)
success_behaviour, _ = check_behaviour(task_id, repo_root)

# Record results
result = EvalResult(
    task_id=task_id,
    success_compile=success_compile,
    success_tests=success_tests,
    success_behaviour=success_behaviour,
    success_static=success_static,
    steps=step_count,
)
```

Test-writing tasks use the same validation pipeline as bug-fixing tasks, ensuring consistency and comprehensive quality checks.

## Success Criteria Summary

A test-writing task is considered successful if:

1. ✅ **Compilation:** Test file has valid Python syntax
2. ✅ **Collection:** Pytest can discover and parse tests
3. ✅ **Execution:** Tests run without crashes (pass/fail both acceptable)
4. ✅ **Static Analysis:** Code passes linting (ruff/flake8)
5. ✅ **Behavior:** Pattern validation confirms correct test structure

All five criteria must pass for a test-writing task to succeed.
