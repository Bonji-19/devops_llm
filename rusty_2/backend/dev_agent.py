"""DevAgent - Autonomous development assistant that uses LLM and MCP tools."""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..common.conversation import Conversation
from ..common.llm_client import ModelClient, get_model_config
from ..common.mcp_client import MCPToolClient
from ..common.messages import assistant_message, system_message, tool_message, user_message


@dataclass
class DevAgentConfig:
    """
    Configuration for the DevAgent.
    
    Attributes:
        max_steps: Maximum number of agent iterations before stopping
        backend_name: Label for the LLM backend (e.g., "gemini", "openai")
        git_mcp_url: Base URL of the Git MCP server
        allowed_tools: Optional set of tool names to allow (filters MCP tools)
    """
    
    max_steps: int = 20
    backend_name: str = "openai"
    git_mcp_url: str = ""
    allowed_tools: Optional[set[str]] = None


@dataclass
class DevAgentResult:
    """
    Result of running a DevAgent task.
    
    Attributes:
        success: Whether the task was completed successfully
        steps: Number of steps executed
        conversation: The final conversation state
        error: Optional error message if the task failed
    """
    
    success: bool
    steps: int
    conversation: Conversation
    error: Optional[str] = None


class DevAgent:
    """
    Autonomous development assistant that uses LLM and MCP tools.
    
    The DevAgent maintains a conversation, calls an LLM to generate responses,
    and executes tools (especially Git MCP server tools) to perform development tasks.
    """
    
    def __init__(
        self,
        model_client: ModelClient,
        mcp_tool_client: MCPToolClient,
        config: DevAgentConfig,
    ):
        """
        Initialize the DevAgent.
        
        Args:
            model_client: ModelClient instance for LLM calls
            mcp_tool_client: MCPToolClient instance for tool execution
            config: DevAgent configuration
        """
        self.model_client = model_client
        self.mcp_tool_client = mcp_tool_client
        self.config = config
        self._available_tools: Optional[list[dict]] = None
    
    async def _get_available_tools(self) -> list[dict]:
        """
        Get the list of available tools from the MCP server.
        
        Caches the result after first call.
        
        Returns:
            list[dict]: List of tool specifications in OpenAI format
        """
        if self._available_tools is None:
            self._available_tools = await self.mcp_tool_client.list_tools()
        return self._available_tools
    
    async def run_step(self, conversation: Conversation) -> None:
        """
        Perform one agent iteration.
        """
        # Get available tools from MCP
        tools = await self._get_available_tools()

        # Decide whether to allow tools this turn.
        # If we already have a tool result in the conversation,
        # don't expose tools again. This forces the model to
        # reason in natural language instead of looping on tools.
        allow_tools = True
        for msg in reversed(conversation.messages):
            if msg.get("role") == "assistant":
                content = msg.get("content", "")
                if isinstance(content, str) and content.startswith("Tool result:"):
                    allow_tools = False
                    break

        # Call LLM with or without tools depending on allow_tools
        response = await self.model_client.generate(
            messages=conversation.messages,
            tools=tools if (tools and allow_tools) else None,
        )

        
        # Extract the assistant message from the response
        if "choices" not in response or not response["choices"]:
            raise ValueError("LLM response has no choices")
        
        choice = response["choices"][0]
        assistant_msg = choice.get("message", {})
        
        # --- IMPORTANT: normalize assistant content to a string ---
        raw_content = assistant_msg.get("content", "")

        # If the model only issued tool_calls, content is often None.
        # In that case, treat it as an empty string instead of "None".
        if raw_content is None:
            content_text = ""
        elif isinstance(raw_content, list):
            parts: list[str] = []
            for part in raw_content:
                if isinstance(part, dict) and part.get("type") == "text":
                    parts.append(part.get("text", ""))
                else:
                    parts.append(str(part))
            content_text = "\n".join(parts)
        else:
            content_text = str(raw_content)

        # ---------------------------------------------------------
        
        # Build the assistant message dict
        assistant_message_dict = {
            "role": "assistant",
            "content": content_text,
        }
        
        # Add tool calls if present
        tool_calls = assistant_msg.get("tool_calls")
        if tool_calls:
            assistant_message_dict["tool_calls"] = tool_calls
        
        # Append assistant message to conversation
        conversation.append(assistant_message_dict)
        
        # Execute tool calls if any
        if tool_calls:
            for tool_call in tool_calls:
                try:
                    # Execute the tool via MCP client
                    tool_results = await self.mcp_tool_client.call_tool_from_openai_tool_call(
                        tool_call
                    )
                    
                    # Convert tool results to a single content string
                    content_parts = []
                    for result in tool_results:
                        result_type = result.get("type", "text")
                        result_data = result.get("data", "")
                        
                        if result_type == "text":
                            content_parts.append(str(result_data))
                        elif result_type == "json":
                            content_parts.append(json.dumps(result_data, indent=2))
                        else:
                            content_parts.append(f"[{result_type}]: {result_data}")
                    
                    tool_content = "\n\n".join(content_parts) if content_parts else ""
                    
                    # Get tool call ID for the tool message
                    tool_call_id = None
                    if "id" in tool_call:
                        tool_call_id = tool_call["id"]
                    elif "function" in tool_call and "name" in tool_call["function"]:
                        tool_call_id = tool_call["function"]["name"]
                    
                    # Append tool message to conversation
                    tool_msg = tool_message(
                        content=tool_content,
                        tool_call_id=tool_call_id,
                    )
                    conversation.append(tool_msg)
                    
                except Exception as e:
                    # If tool execution fails, append error message
                    error_msg = tool_message(
                        content=f"Error executing tool: {str(e)}",
                        tool_call_id=tool_call.get("id") if "id" in tool_call else None,
                    )
                    conversation.append(error_msg)



def create_initial_conversation(task_description: str, repo_root: str) -> Conversation:
    """
    Create a Conversation with system and initial user messages.
    
    The system message describes the agent's role as an autonomous local
    development assistant that works on a local repository and must use
    tools to inspect/modify files, run tests, and run static checks.
    
    Args:
        task_description: The task description from the user
        repo_root: Path to the repository root directory
        
    Returns:
        Conversation: Initialized conversation with system and user messages
    """
    repo_path = Path(repo_root).resolve()
    
    system_content = f"""You are an autonomous local development assistant.

You are working on a local repository located at: {repo_path}

Your responsibilities:
- Use the available tools to inspect and modify files in the repository
- Run tests to verify changes work correctly
- Run static checks (linters, type checkers, etc.) to ensure code quality
- Keep changes minimal and focused on the task at hand
- Stop when tests and checks pass and the task appears solved

You have access to Git MCP server tools that allow you to:
- Read and modify files
- Run commands
- Check git status
- And perform other repository operations

For each task:
1. Use tools as needed to gather information (e.g., list files, inspect tests, run tests).
2. Then produce a clear natural-language explanation of what you found.
3. Only call tools again if you really need more information.
4. When you believe you have answered the task, end your final message with the exact phrase: "Task completed".

Always verify your work by running tests and checks before considering the task complete."""


    
    conversation = Conversation()
    conversation.append(system_message(system_content))
    conversation.append(user_message(task_description))
    
    return conversation


async def run_task(
    task_description: str,
    repo_root: str,
    config: DevAgentConfig,
) -> DevAgentResult:
    """
    Run a DevAgent task to completion.
    
    This function:
    1. Creates ModelClient and MCPToolClient from the config
    2. Builds the initial Conversation
    3. Loops up to max_steps calling DevAgent.run_step
    4. Uses a simple stopping heuristic based on assistant messages
    5. Returns DevAgentResult with the final conversation state
    
    Args:
        task_description: Description of the task to complete
        repo_root: Path to the repository root directory
        config: DevAgent configuration
        
    Returns:
        DevAgentResult: Result containing success status, steps executed, and final conversation
    """
    try:
        # Create ModelClient using config.backend_name
        # get_model_config will use appropriate defaults (gpt-4o-mini for OpenAI)
        model_config = get_model_config(
            backend_name=config.backend_name,
            model_name=os.getenv("LLM_MODEL_NAME"),  # Use env var if set, otherwise get_model_config uses defaults
        )
        model_client = ModelClient(model_config)
        
        # Create MCPToolClient
        mcp_tool_client = MCPToolClient(
            base_url=config.git_mcp_url,
            allowed_tools=config.allowed_tools,
            default_repo_path=str(Path(repo_root).resolve()),
        )
        
        # Create DevAgent
        agent = DevAgent(
            model_client=model_client,
            mcp_tool_client=mcp_tool_client,
            config=config,
        )
        
        # Create initial conversation
        conversation = create_initial_conversation(task_description, repo_root)
        
        # Run agent steps
        steps = 0
        for step in range(config.max_steps):
            await agent.run_step(conversation)
            steps += 1
            
            # Check if task is complete
            # Look at the most recent assistant message for completion phrases
            messages = conversation.messages
            if messages:
                # Find the most recent assistant message (may not be the last if tool messages follow)
                for message in reversed(messages):
                    if message.get("role") == "assistant":
                        content = message.get("content", "").lower()
                        completion_phrases = [
                            "i have completed the task",
                            "task completed",
                            "task is complete",
                            "i have finished",
                            "task finished",
                            "completed the task",
                        ]
                        
                        if any(phrase in content for phrase in completion_phrases):
                            return DevAgentResult(
                                success=True,
                                steps=steps,
                                conversation=conversation,
                            )
                        break  # Only check the most recent assistant message
        
        # If we've exhausted max_steps, return with success=False
        return DevAgentResult(
            success=False,
            steps=steps,
            conversation=conversation,
            error=f"Reached maximum steps ({config.max_steps}) without completion",
        )
        
    except Exception as e:
        # Return error result
        return DevAgentResult(
            success=False,
            steps=steps if "steps" in locals() else 0,
            conversation=conversation if "conversation" in locals() else Conversation(),
            error=str(e),
        )

