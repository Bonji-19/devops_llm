import asyncio
from pathlib import Path
import sys

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rusty_2.common.mcp_client import MCPToolClient


async def main():
    repo_root = str(REPO_ROOT)

    # base_url for stdio: our MCP client will spawn mcp-server-git itself
    base_url = "stdio://python:-m:mcp_server_git:--repository:" + repo_root

    client = MCPToolClient(base_url=base_url)

    print("Listing tools from mcp-server-git...")
    tools = await client.list_tools()
    print(f"Found {len(tools)} tools.")
    for t in tools[:10]:
        print(" -", t["function"]["name"])

    # Try calling a simple tool (pick a 'status'-like one if it exists)
    status_tool = None
    for t in tools:
        name = t["function"]["name"]
        if "status" in name.lower():
            status_tool = name
            break

    if not status_tool:
        print("No status-like tool found, skipping call_tool test.")
        return

    print(f"\nCalling tool: {status_tool}")
    result_blocks = await client.call_tool(
        status_tool,
        {"repo_path": repo_root},
    )
    for block in result_blocks:
        print(block["type"], "=>", str(block["data"])[:300])


if __name__ == "__main__":
    asyncio.run(main())
