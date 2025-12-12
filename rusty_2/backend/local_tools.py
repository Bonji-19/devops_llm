"""Local tools for file I/O and unified diff patch application."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from rusty_2.common.unified_diff import UnifiedDiff, apply as apply_unified_diff


# Tool specs in OpenAI "tools" format
LOCAL_TOOL_SPECS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories in a directory. Use this to explore the repository structure.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the directory, relative to the repo root. Use '.' for the repo root.",
                        "default": ".",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a UTF-8 text file from the repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file, relative to the repo root.",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "apply_unified_diff",
            "description": (
                "Apply a unified diff patch to a file in the repository. "
                "Use this for small, focused edits. The diff should be a standard "
                "unified diff with --- / +++ headers and @@ hunks."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to patch, relative to the repo root.",
                    },
                    "diff": {
                        "type": "string",
                        "description": "Unified diff patch to apply to that file.",
                    },
                    "strict": {
                        "type": "boolean",
                        "description": "If true, apply hunks strictly; if false, try to locate hunks fuzzily.",
                        "default": True,
                    },
                },
                "required": ["path", "diff"],
            },
        },
    },
]


@dataclass
class LocalToolExecutor:
    """Executes local tools like read_file and apply_unified_diff."""
    repo_root: Path

    def _resolve_path(self, relative: str) -> Path:
        """Resolve a relative path safely under the repo root."""
        p = (self.repo_root / relative).resolve()
        if not str(p).startswith(str(self.repo_root.resolve())):
            raise ValueError(f"Path {relative!r} escapes the repository root")
        return p

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Execute a local tool and return a list of content blocks
        in the same shape as MCPToolClient.call_tool(...):

        [
          {"type": "text", "data": "..."},
          {"type": "json", "data": {...}},
          ...
        ]
        """
        if name == "list_files":
            return await self._list_files(arguments)
        elif name == "read_file":
            return await self._read_file(arguments)
        elif name == "apply_unified_diff":
            return await self._apply_unified_diff(arguments)
        else:
            raise ValueError(f"Unknown local tool: {name}")

    async def _list_files(self, args: Dict[str, Any]) -> List[Dict[str, Any]]:
        """List files and directories in a directory."""
        dir_path_str = args.get("path", ".")
        dir_path = self._resolve_path(dir_path_str)
        
        if not dir_path.exists():
            return [{
                "type": "text",
                "data": f"[list_files] Directory not found: {dir_path_str}",
            }]
        
        if not dir_path.is_dir():
            return [{
                "type": "text",
                "data": f"[list_files] Path is not a directory: {dir_path_str}",
            }]
        
        try:
            items = []
            for item in sorted(dir_path.iterdir()):
                # Skip .git directory to avoid clutter
                if item.name == ".git":
                    continue
                
                item_type = "directory" if item.is_dir() else "file"
                items.append(f"{item_type}: {item.name}")
            
            if not items:
                result_text = f"[list_files] Directory '{dir_path_str}' is empty"
            else:
                result_text = f"[list_files] Contents of '{dir_path_str}':\n" + "\n".join(items)
            
            return [{"type": "text", "data": result_text}]
        except Exception as e:
            return [{
                "type": "text",
                "data": f"[list_files] Error listing directory {dir_path_str}: {e}",
            }]

    async def _read_file(self, args: Dict[str, Any]) -> List[Dict[str, Any]]:
        path = self._resolve_path(args["path"])
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return [{
                "type": "text",
                "data": f"[read_file] File not found: {args['path']}",
            }]
        return [{
            "type": "text",
            "data": text,
        }]

    async def _apply_unified_diff(self, args: Dict[str, Any]) -> List[Dict[str, Any]]:
        path = self._resolve_path(args["path"])
        diff_str: str = args["diff"]
        strict: bool = bool(args.get("strict", True))

        try:
            udiff = UnifiedDiff.from_string(diff_str)
            # Apply in-place: from_file/to_file both this path
            apply_unified_diff(udiff, from_file=path, to_file=path, strict=strict)
            msg = f"[apply_unified_diff] Patch applied successfully to {args['path']}"
            return [{"type": "text", "data": msg}]
        except Exception as e:
            return [{
                "type": "text",
                "data": f"[apply_unified_diff] Failed to apply patch to {args['path']}: {e}",
            }]
