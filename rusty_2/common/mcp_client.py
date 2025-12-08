"""MCP (Model Context Protocol) client for connecting to MCP servers and exposing tools."""

import json
from typing import Optional

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
except ImportError:
    raise ImportError(
        "mcp package is required. Install it with: pip install mcp"
    )


# Try to import stdio_client function
# According to MCP Python SDK, stdio_client is a function in mcp.client.stdio
stdio_client_func = None
try:
    from mcp.client.stdio import stdio_client as stdio_client_func
except ImportError:
    try:
        from mcp.client import stdio
        if hasattr(stdio, 'stdio_client'):
            stdio_client_func = stdio.stdio_client
    except ImportError:
        pass  # Will handle error later if stdio transport is needed


class MCPToolClient:
    """
    Client for connecting to MCP servers and exposing their tools in OpenAI-compatible format.
    
    This client connects to an MCP server (e.g., Git MCP server) via HTTP and provides
    methods to list and call tools, converting MCP tool responses into a format compatible
    with OpenAI's tool calling interface.
    """
    
    def __init__(
        self,
        base_url: str,
        authorization: Optional[str] = None,
        allowed_tools: Optional[set[str]] = None,
        default_repo_path: Optional[str] = None,
    ):
        """
        Initialize the MCP tool client.
        
        Args:
            base_url: Base URL of the MCP server
            authorization: Optional authorization header value
            allowed_tools: Optional set of tool names to allow (filters list_tools)
        """
        self.base_url = base_url
        self.authorization = authorization
        self.allowed_tools = allowed_tools
        self.default_repo_path = default_repo_path
    
    def _get_transport_context(self):
        """
        Create and return the transport context manager.

        For stdio, this builds a StdioServerParameters object and passes it
        to stdio_client(). The expected base_url format is:

            stdio://python:-m:mcp_server_git:--repository:<repo_path>

        On Windows, <repo_path> contains a colon (C:\...), so we need to
        carefully reconstruct it instead of blindly splitting on ':'.
        """
        if self.base_url.startswith("stdio://"):
            if stdio_client_func is None:
                raise ImportError(
                    "stdio_client function not available. "
                    "Cannot use stdio:// URLs. "
                    "Please ensure mcp package is installed: pip install mcp"
                )

            command_str = self.base_url[len("stdio://") :]
            parts = command_str.split(":")

            if not parts:
                raise ValueError("Invalid stdio URL, no command specified")

            command = parts[0]

            # No args at all
            if len(parts) == 1:
                args: list[str] = []
            # Our normal pattern:
            # python:-m:mcp_server_git:--repository:<repo_path>
            elif len(parts) >= 5 and parts[1:4] == ["-m", "mcp_server_git", "--repository"]:
                # Rebuild the repo path from the remaining pieces, re-inserting ':'
                repo_path = ":".join(parts[4:])
                args = ["-m", "mcp_server_git", "--repository", repo_path]
            else:
                # Generic fallback: no special handling, just pass everything after command
                args = parts[1:]

            server_params = StdioServerParameters(
                command=command,
                args=args,
            )

            # stdio_client(server_params) returns an async context manager
            # yielding (read, write) streams
            return stdio_client_func(server_params)

        # HTTP transport not implemented yet
        raise NotImplementedError(
            f"HTTP transport not yet implemented. "
            f"Please use stdio:// URLs for now. "
            f"Requested URL: {self.base_url}"
        )


    
    async def list_tools(self) -> list[dict]:
        """
        Connect to the MCP server and list available tools.
        
        Returns a list of tool specifications in OpenAI-compatible format,
        each containing name, description, and parameters (JSON schema).
        If allowed_tools is set, only tools in that set are returned.
        
        Returns:
            list[dict]: List of tool specifications as dictionaries
            
        Raises:
            Exception: If connection to MCP server fails
        """
        try:
            # Use the transport context manager
            # stdio_client returns a context manager that yields (read, write) streams
            async with self._get_transport_context() as streams:
                # Unpack the (read, write) tuple
                read, write = streams
                
                # Create ClientSession with read and write streams
                async with ClientSession(read, write) as session:
                    # Initialize the session
                    await session.initialize()
                    
                    # List tools from the MCP server
                    tools_response = await session.list_tools()
                    
                    # Convert MCP Tool objects to OpenAI-compatible dict format
                    tool_specs = []
                    for tool in tools_response.tools:
                        # Filter by allowed_tools if set
                        if self.allowed_tools is not None and tool.name not in self.allowed_tools:
                            continue
                        
                        # Convert to OpenAI tool format
                        tool_spec = {
                            "type": "function",
                            "function": {
                                "name": tool.name,
                                "description": tool.description or "",
                                "parameters": tool.inputSchema if hasattr(tool, "inputSchema") else {},
                            }
                        }
                        tool_specs.append(tool_spec)
                    
                    return tool_specs
        except ExceptionGroup as eg:
            # Handle ExceptionGroup (TaskGroup errors) - Python 3.11+
            errors = list(eg.exceptions)
            error_msgs = [f"{type(e).__name__}: {str(e)}" for e in errors]
            raise RuntimeError(
                f"Failed to list tools from MCP server at {self.base_url}. "
                f"Errors ({len(errors)}): {'; '.join(error_msgs)}"
            ) from eg
        except Exception as e:
            # Re-raise with more context
            import traceback
            # Check if it's an ExceptionGroup-like error (for older Python or different error types)
            if "TaskGroup" in str(type(e)) or "unhandled errors" in str(e):
                raise RuntimeError(
                    f"Failed to list tools from MCP server at {self.base_url}. "
                    f"TaskGroup/async error: {type(e).__name__}: {str(e)}\n"
                    f"Traceback: {traceback.format_exc()}"
                ) from e
            raise RuntimeError(
                f"Failed to list tools from MCP server at {self.base_url}: {type(e).__name__}: {str(e)}\n"
                f"Traceback: {traceback.format_exc()}"
            ) from e
    
    async def call_tool(
        self,
        name: str,
        arguments: Optional[dict] = None,
    ) -> list[dict]:
        """
        Call a tool on the MCP server with the given arguments.
        
        Connects to the MCP server, calls the specified tool, and maps the
        returned content blocks into a list of dictionaries with type and data fields.
        
        Args:
            name: Name of the tool to call
            arguments: Optional dictionary of tool arguments
            
        Returns:
            list[dict]: List of content blocks, each with:
                - type: "text" or "json" or other content type
                - data: String or JSON object containing the content
                
        Raises:
            Exception: If connection fails or tool call fails
        """
        # Normalize arguments
        if arguments is None:
            arguments = {}

        # Auto-inject repo_path if not given and we have a default
        if "repo_path" not in arguments and self.default_repo_path is not None:
            arguments["repo_path"] = self.default_repo_path
        
        try:
            # Use the transport context manager
            async with self._get_transport_context() as streams:
                # Unpack the (read, write) tuple
                read, write = streams
                
                # Create ClientSession with read and write streams
                async with ClientSession(read, write) as session:
                    # Initialize the session
                    await session.initialize()
                    
                    # Call the tool
                    result = await session.call_tool(name, arguments)
                    
                    # Map content blocks to dict format
                    content_blocks = []
                    for content in result.content or []:
                        if isinstance(content, TextContent):
                            content_blocks.append({
                                "type": "text",
                                "data": content.text,
                            })
                        elif isinstance(content, ImageContent):
                            # Handle image content if needed
                            content_blocks.append({
                                "type": "image",
                                "data": content.data if hasattr(content, "data") else str(content),
                            })
                        elif isinstance(content, EmbeddedResource):
                            # Handle embedded resources
                            content_blocks.append({
                                "type": "resource",
                                "data": {
                                    "uri": content.uri if hasattr(content, "uri") else None,
                                    "mimeType": content.mimeType if hasattr(content, "mimeType") else None,
                                },
                            })
                        else:
                            # Fallback: convert to string
                            content_blocks.append({
                                "type": "text",
                                "data": str(content),
                            })
                    
                    return content_blocks
        except ExceptionGroup as eg:
            # Handle ExceptionGroup (TaskGroup errors) - Python 3.11+
            errors = list(eg.exceptions)
            error_msgs = [f"{type(e).__name__}: {str(e)}" for e in errors]
            raise RuntimeError(
                f"Failed to call tool '{name}' on MCP server at {self.base_url}. "
                f"Errors ({len(errors)}): {'; '.join(error_msgs)}"
            ) from eg
        except Exception as e:
            # Re-raise with more context
            import traceback
            # Check if it's an ExceptionGroup-like error (for older Python or different error types)
            if "TaskGroup" in str(type(e)) or "unhandled errors" in str(e):
                raise RuntimeError(
                    f"Failed to call tool '{name}' on MCP server at {self.base_url}. "
                    f"TaskGroup/async error: {type(e).__name__}: {str(e)}\n"
                    f"Traceback: {traceback.format_exc()}"
                ) from e
            raise RuntimeError(
                f"Failed to call tool '{name}' on MCP server at {self.base_url}: {type(e).__name__}: {str(e)}\n"
                f"Traceback: {traceback.format_exc()}"
            ) from e
    
    async def call_tool_from_openai_tool_call(
        self,
        tool_call: dict,
    ) -> list[dict]:
        """
        Call an MCP tool using an OpenAI tool call structure.
        
        This is a convenience method that extracts the tool name and arguments
        from an OpenAI-style tool call dictionary and calls the MCP tool.
        
        Args:
            tool_call: Dictionary with OpenAI tool call structure:
                - function.name: Name of the tool
                - function.arguments: JSON string of tool arguments
                
        Returns:
            list[dict]: List of content blocks from the tool call
            
        Raises:
            ValueError: If tool_call structure is invalid
            Exception: If tool call fails
        """
        # Extract function name
        if "function" not in tool_call:
            raise ValueError("tool_call must have a 'function' field")
        
        function = tool_call["function"]
        if "name" not in function:
            raise ValueError("tool_call.function must have a 'name' field")
        
        tool_name = function["name"]
        
        # Extract and parse arguments
        arguments = None
        if "arguments" in function:
            args_str = function["arguments"]
            if isinstance(args_str, str):
                try:
                    arguments = json.loads(args_str)
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON in tool_call.function.arguments: {e}")
            elif isinstance(args_str, dict):
                arguments = args_str
            else:
                raise ValueError("tool_call.function.arguments must be a string or dict")
        
        return await self.call_tool(tool_name, arguments)

