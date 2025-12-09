import sys
from pathlib import Path
import asyncio

# Ensure project root is on sys.path so `import rusty_2...` works
PROJECT_ROOT = Path(__file__).resolve().parents[1]  # .../devops_llm
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rusty_2.backend.local_tools import LocalToolExecutor


async def main() -> None:
    # Repo root = project root
    repo_root = PROJECT_ROOT
    print(f"Repo root: {repo_root}")

    # Instantiate the local tool executor
    executor = LocalToolExecutor(repo_root=repo_root)

    # We'll create a small temporary file inside the repo
    rel_path = "tmp_unified_diff_test.txt"
    file_path = repo_root / rel_path

    original_content = "line1\nline2\nline3\n"
    file_path.write_text(original_content, encoding="utf-8")

    print("\n=== Original file content ===")
    print(file_path.read_text(encoding="utf-8"))

    # A simple unified diff that changes 'line2' -> 'LINE2'
    diff_text = """--- tmp_unified_diff_test.txt
+++ tmp_unified_diff_test.txt
@@ -1,3 +1,3 @@
 line1
-line2
+LINE2
 line3
"""

    print("\n=== Applying unified diff via apply_unified_diff tool ===")
    apply_results = await executor.call_tool(
        "apply_unified_diff",
        {
            "path": rel_path,  # relative to repo root
            "diff": diff_text,
            "strict": True,    # require exact match of hunk
        },
    )

    print("Tool output:")
    for r in apply_results:
        print(f"- {r.get('type')}: {r.get('data')}")

    print("\n=== File content after patch ===")
    print(file_path.read_text(encoding="utf-8"))

    print("\n=== Reading file via read_file tool ===")
    read_results = await executor.call_tool(
        "read_file",
        {"path": rel_path},
    )

    for r in read_results:
        print(f"- {r.get('type')}: {r.get('data')}")

    print("\nDone. You can delete tmp_unified_diff_test.txt if you like.")


if __name__ == "__main__":
    asyncio.run(main())
