import sys
from pathlib import Path
import asyncio

# Ensure project root is on sys.path so `import rusty_2...` works
PROJECT_ROOT = Path(__file__).resolve().parents[1]  # .../devops_llm
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rusty_2.backend.dev_agent import DevAgentConfig, run_task


async def main() -> None:
    # Repo root = project root
    repo_root = PROJECT_ROOT
    print(f"Repo root: {repo_root}")

    # Prepare a small test file the agent should edit
    rel_path = "tmp_agent_edit_test.txt"
    file_path = repo_root / rel_path
    file_path.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    print("\n=== Initial file content ===")
    print(file_path.read_text(encoding="utf-8"))

    # MCP Git URL (same pattern you use elsewhere)
    git_mcp_url = f"stdio://python:-m:mcp_server_git:--repository:{repo_root}"

    # DevAgent config: few steps, OpenAI backend
    config = DevAgentConfig(
        max_steps=4,
        backend_name="openai",
        git_mcp_url=git_mcp_url,
    )

    # Task: explicitly tell the agent to use read_file + apply_unified_diff
    task_description = f"""
You are working in this repository.

File to modify: {rel_path}

1. Use the read_file tool to read the current contents of {rel_path}.
2. Then use apply_unified_diff to change the line 'beta' to 'BETA'.
   The unified diff should have proper --- / +++ headers and @@ hunk.
3. After applying the patch, briefly confirm what you changed and say "Task completed".
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
    for m in result.conversation.messages[-6:]:
        print(f"[{m['role']}] {str(m.get('content'))[:500]}")

    print("\n=== File content after agent run ===")
    print(file_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    asyncio.run(main())
