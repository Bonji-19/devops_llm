import sys
from pathlib import Path

repo_root = str(Path(".").resolve())

git_mcp_url = (
    "stdio://python:-m:mcp_server_git:--repository:" + repo_root
)

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import asyncio

from rusty_2.backend.dev_agent import DevAgentConfig, run_task
from rusty_2.common.settings import load_env


async def main():
    load_env()

    repo_root = str(Path(".").resolve())
    git_mcp_url = (
        "stdio://python:-m:mcp_server_git:--repository:" + repo_root
    )

    config = DevAgentConfig(
        max_steps=6,
        backend_name="openai",  # Use OpenAI instead of Gemini
        git_mcp_url=git_mcp_url,
    )

    task = "Inspect this repository and briefly describe what the test files do."

    try:
        result = await run_task(task_description=task, repo_root=repo_root, config=config)
    except Exception as exc:
        import traceback
        print("FATAL EXCEPTION IN run_task:")
        traceback.print_exc()
        return

    print("Success:", result.success)
    print("Steps:", result.steps)
    print("Error:", result.error)

    print("\n--- Last messages ---")
    for msg in result.conversation.messages[-5:]:
        role = msg["role"]
        content = msg["content"]
        print(f"[{role}] {content[:300]}\n")


if __name__ == "__main__":
    asyncio.run(main())
