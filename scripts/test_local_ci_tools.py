import sys
from pathlib import Path
import asyncio

# Ensure project root is on sys.path so `import rusty_2...` works
PROJECT_ROOT = Path(__file__).resolve().parents[1]  # .../devops_llm
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rusty_2.backend.local_tools import LocalToolExecutor  # type: ignore[import]


async def main() -> None:
    repo_root = PROJECT_ROOT
    print(f"Repo root: {repo_root}")

    executor = LocalToolExecutor(repo_root=repo_root)

    # 1) Test write_file
    print("\n=== Testing write_file + read_file ===")
    rel_path = "tmp_local_tools_new_file.txt"
    content = "hello\nthis is a new file\ncreated by write_file\n"

    # Call write_file
    result = await executor.call_tool(
        "write_file",
        {"path": rel_path, "content": content, "overwrite": True},
    )
    for block in result:
        print(f"- {block['type']}: {block['data']}")

    # Read it back
    print("\nReading file back with read_file...")
    result = await executor.call_tool("read_file", {"path": rel_path})
    for block in result:
        print(f"- {block['type']}: {block['data']}")

    # 2) Test run_tests
    print("\n=== Testing run_tests ===")
    result = await executor.call_tool("run_tests", {})
    for block in result:
        # Only print a prefix so it doesn't spam
        data = str(block["data"])
        print(f"- {block['type']}: {data[:500]}")
        if len(data) > 500:
            print("  ...[truncated]")

    # 3) Test run_linter
    print("\n=== Testing run_linter ===")
    result = await executor.call_tool("run_linter", {"target": "rusty_2"})
    for block in result:
        data = str(block["data"])
        print(f"- {block['type']}: {data[:500]}")
        if len(data) > 500:
            print("  ...[truncated]")

    print("\nDone. You can delete tmp_local_tools_new_file.txt if you like.")


if __name__ == "__main__":
    asyncio.run(main())
