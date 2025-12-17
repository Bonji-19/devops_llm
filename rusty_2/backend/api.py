"""FastAPI backend for DevAgent."""

from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from ..common.settings import load_env
from .dev_agent import DevAgentConfig, run_task

# Load environment variables at module import
load_env()

# Create FastAPI app
app = FastAPI(
    title="DevAgent API",
    description="API for autonomous development assistant using LLM and MCP tools",
    version="1.0.0",
)


class MessageModel(BaseModel):
    """Model for a chat message."""
    
    role: str
    content: str
    tool_call_id: Optional[str] = None


class DevAgentRunRequest(BaseModel):
    """Request model for running a DevAgent task."""
    
    task_description: str
    repo_root: str
    git_mcp_url: str
    max_steps: int = 30
    conversation_history: Optional[list[MessageModel]] = None


class DevAgentRunResponse(BaseModel):
    """Response model for DevAgent task execution."""
    
    success: bool
    steps: int
    error: Optional[str] = None
    messages: list[MessageModel]


@app.post("/dev-agent/run", response_model=DevAgentRunResponse)
async def run_dev_agent(request: DevAgentRunRequest) -> DevAgentRunResponse:
    """
    Run a DevAgent task.
    
    This endpoint accepts a task description and repository information,
    executes the DevAgent, and returns the results including the full
    conversation history.
    
    Args:
        request: DevAgentRunRequest containing task details
        
    Returns:
        DevAgentRunResponse with execution results and conversation
        
    Raises:
        HTTPException: If task execution fails
    """
    try:
        # Build DevAgentConfig from request
        config = DevAgentConfig(
            max_steps=request.max_steps,
            git_mcp_url=request.git_mcp_url,
            backend_name="openai",  # Default backend, can be enhanced later
        )
        
        # Convert conversation history if provided
        existing_conversation = None
        if request.conversation_history:
            from ..common.conversation import Conversation
            message_dicts = []
            for msg_model in request.conversation_history:
                msg_dict = {
                    "role": msg_model.role,
                    "content": msg_model.content,
                }
                if msg_model.tool_call_id:
                    msg_dict["tool_call_id"] = msg_model.tool_call_id
                message_dicts.append(msg_dict)
            existing_conversation = Conversation(messages=message_dicts)
        
        # Run the task
        result = await run_task(
            task_description=request.task_description,
            repo_root=request.repo_root,
            config=config,
            existing_conversation=existing_conversation,
        )
        
        # Serialize conversation messages to MessageModel list
        message_models = []
        for msg in result.conversation.messages:
            message_model = MessageModel(
                role=msg.get("role", "unknown"),
                content=msg.get("content", ""),
                tool_call_id=msg.get("tool_call_id"),
            )
            message_models.append(message_model)
        
        # Build and return response
        return DevAgentRunResponse(
            success=result.success,
            steps=result.steps,
            error=result.error,
            messages=message_models,
        )
        
    except Exception as e:
        # Handle errors and return appropriate HTTP response
        raise HTTPException(
            status_code=500,
            detail=f"Error executing DevAgent task: {str(e)}",
        )


@app.get("/")
async def root():
    """Root endpoint providing API information."""
    return {
        "name": "DevAgent API",
        "version": "1.0.0",
        "description": "API for autonomous development assistant",
        "endpoints": {
            "POST /dev-agent/run": "Execute a DevAgent task",
        },
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}

