import json
import requests
from pathlib import Path

def main():
    repo_root = str(Path(__file__).resolve().parents[1])
    git_mcp_url = "stdio://python:-m:mcp_server_git:--repository:" + repo_root

    payload = {
        "task_description": "Inspect this repository and briefly describe what the test files do.",
        "repo_root": repo_root,
        "git_mcp_url": git_mcp_url,
        "max_steps": 4,
    }

    url = "http://127.0.0.1:8000/dev-agent/run"

    resp = requests.post(url, json=payload)
    print("Status:", resp.status_code)
    data = resp.json()
    print(json.dumps(data, indent=2)[:2000])

if __name__ == "__main__":
    main()
