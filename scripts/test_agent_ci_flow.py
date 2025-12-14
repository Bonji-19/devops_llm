import sys
from pathlib import Path
import asyncio

# Ensure project root on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rusty_2.backend.dev_agent import DevAgentConfig, run_task  # type: ignore[import]


async def main() -> None:
    repo_root = PROJECT_ROOT
    print(f"Repo root: {repo_root}")

    # MCP Git URL (same style as before)
    git_mcp_url = f"stdio://python:-m:mcp_server_git:--repository:{repo_root}"

    config = DevAgentConfig(
        max_steps=8,
        backend_name="openai",
        git_mcp_url=git_mcp_url,
    )

    # Task: create a simple file via write_file, then run_tests.
    # (Even if there are no tests, run_tests should still execute.)
    task_description = """
You are working in this repository.

1. Use the write_file tool to create or overwrite a file named tmp_agent_ci_demo.txt
   in the repo root, with the following exact content:

   hello from dev agent
   this file was created with write_file

2. After creating the file, call run_tests to run the test suite.
3. Briefly summarize the test outcome (exit code and any important info).
4. Then say exactly "Task completed" at the end of your final message.
"""

    result = await run_task(
        task_description=task_description,
        repo_root=str(repo_root),
        config=config,
    )

    print("\n=== Agent result ===")
    print("Success:", result.success)
    print("Steps:", result.steps)
    print("Error:", result.error)

    print("\n=== Last few messages ===")
    for m in result.conversation.messages[-8:]:
        role = m.get("role")
        content = str(m.get("content"))[:600]
        print(f"[{role}] {content}")
        print("-" * 60)

    # Show final file content if it exists
    file_path = repo_root / "tmp_agent_ci_demo.txt"
    if file_path.exists():
        print("\n=== Final file content (tmp_agent_ci_demo.txt) ===")
        print(file_path.read_text(encoding="utf-8"))
    else:
        print("\nFile tmp_agent_ci_demo.txt was not created.")


if __name__ == "__main__":
    asyncio.run(main())
