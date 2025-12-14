"""Local tools for file I/O and unified diff patch application."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from rusty_2.common.unified_diff import UnifiedDiff, apply as apply_unified_diff

import asyncio
import sys
import traceback
import subprocess


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
        {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a UTF-8 text file in the repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to the repo root.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Full content of the file.",
                    },
                    "overwrite": {
                        "type": "boolean",
                        "description": "If false and the file exists, the tool will fail.",
                        "default": True,
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_tests",
            "description": "Run the test suite with pytest in the repository root.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_linter",
            "description": "Run a linter (e.g. pylint) on the repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "Optional target to lint (e.g. 'rusty_2'). Defaults to the repo root package.",
                        "default": "",
                    }
                },
                "required": [],
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
        elif name == "write_file":
            return await self._write_file(arguments)
        elif name == "run_tests":
            return await self._run_tests(arguments)
        elif name == "run_linter":
            return await self._run_linter(arguments)
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
    async def _write_file(self, args: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create or overwrite a UTF-8 text file in the repository."""
        rel_path = args["path"]
        content = args["content"]
        overwrite = bool(args.get("overwrite", True))

        path = self._resolve_path(rel_path)

        try:
            if path.exists() and not overwrite:
                return [{
                    "type": "text",
                    "data": f"[write_file] File already exists and overwrite=False: {rel_path}",
                }]

            # Ensure parent directory exists
            path.parent.mkdir(parents=True, exist_ok=True)

            path.write_text(content, encoding="utf-8")

            msg = f"[write_file] Wrote {len(content)} characters to {rel_path}"
            return [{"type": "text", "data": msg}]
        except Exception as e:
            return [{
                "type": "text",
                "data": f"[write_file] Error writing file {rel_path}: {e}",
            }]
    async def _run_tests(self, args: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Run pytest in the repository root.

        Uses subprocess.run wrapped in asyncio.to_thread so it also works
        in environments where asyncio.create_subprocess_exec is not implemented.
        """
        python_exe = sys.executable
        cmd = [python_exe, "-m", "pytest"]

        def _run() -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                cmd,
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
            )

        try:
            result = await asyncio.to_thread(_run)
            out = result.stdout or ""
            err = result.stderr or ""

            combined = (
                f"$ {' '.join(cmd)}\n\n"
                f"Exit code: {result.returncode}\n\n"
                f"STDOUT:\n{out}\n\nSTDERR:\n{err}"
            )
            if len(combined) > 8000:
                combined = combined[:8000] + "\n\n...[truncated output]"

            return [{
                "type": "text",
                "data": f"[run_tests] Result:\n{combined}",
            }]
        except FileNotFoundError:
            return [{
                "type": "text",
                "data": "[run_tests] pytest not found. Make sure it is installed in this environment.",
            }]
        except Exception as e:
            tb = traceback.format_exc()
            return [{
                "type": "text",
                "data": f"[run_tests] Error running tests: {e!r}\n\nTraceback:\n{tb}",
            }]



    async def _run_linter(self, args: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Run a linter (e.g. pylint) on the repository or a given target."""
        target = args.get("target", "").strip()
        if not target:
            target = "rusty_2"

        python_exe = sys.executable
        cmd = [python_exe, "-m", "pylint", target]

        def _run() -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                cmd,
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
            )

        try:
            result = await asyncio.to_thread(_run)
            out = result.stdout or ""
            err = result.stderr or ""

            combined = (
                f"$ {' '.join(cmd)}\n\n"
                f"Exit code: {result.returncode}\n\n"
                f"STDOUT:\n{out}\n\nSTDERR:\n{err}"
            )
            if len(combined) > 8000:
                combined = combined[:8000] + "\n\n...[truncated output]"

            return [{
                "type": "text",
                "data": f"[run_linter] Result:\n{combined}",
            }]
        except FileNotFoundError:
            return [{
                "type": "text",
                "data": "[run_linter] pylint not found. Install it (or adjust the tool to your linter of choice).",
            }]
        except Exception as e:
            tb = traceback.format_exc()
            return [{
                "type": "text",
                "data": f"[run_linter] Error running linter: {e!r}\n\nTraceback:\n{tb}",
            }]



