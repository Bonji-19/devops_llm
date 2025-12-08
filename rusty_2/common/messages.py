"""Type system and utilities for chat messages."""

from typing import Literal, Optional, TypedDict


Role = Literal["system", "user", "assistant", "tool"]


class BaseMessage(TypedDict, total=False):
    """
    Base message structure for chat conversations.
    
    Fields:
        role: The role of the message sender
        content: The message content text
        tool_call_id: Optional tool call ID for tool messages
        name: Optional name for tool messages
    """
    
    role: Role
    content: str
    tool_call_id: Optional[str]
    name: Optional[str]


def system_message(content: str) -> dict:
    """
    Create a system message dictionary.
    
    Args:
        content: The system message content
        
    Returns:
        dict: A message dictionary with role "system"
    """
    return {"role": "system", "content": content}


def user_message(content: str) -> dict:
    """
    Create a user message dictionary.
    
    Args:
        content: The user message content
        
    Returns:
        dict: A message dictionary with role "user"
    """
    return {"role": "user", "content": content}


def assistant_message(content: str) -> dict:
    """
    Create an assistant message dictionary.
    
    Args:
        content: The assistant message content
        
    Returns:
        dict: A message dictionary with role "assistant"
    """
    return {"role": "assistant", "content": content}


def tool_message(
    content: str,
    tool_call_id: Optional[str] = None,
    name: Optional[str] = None,
) -> dict:
    """
    Represent tool output as a normal assistant message so the LLM
    sees it as plain text.

    We deliberately *do not* use role="tool" here, because the OpenAI
    API enforces a strict tool-calling protocol that we don't need
    for this project.
    """
    text = f"Tool result:\n{content}"

    return {
        "role": "assistant",
        "content": text,
        # We ignore tool_call_id / name here on purpose – those fields are
        # only valid for true role="tool" messages in the official protocol.
    }



def message_from_dict(data: dict) -> dict:
    """
    Validate and normalize a message dictionary.

    Ensures the message has required fields (role, content) and
    normalizes optional fields (tool_call_id, name).

    Also accepts content as non-string types (e.g. lists of parts)
    and coerces them to a string.
    """
    if not isinstance(data, dict):
        raise ValueError(f"Message must be a dictionary, got {type(data)}")
    
    # Validate role
    if "role" not in data:
        raise ValueError("Message must have a 'role' field")
    
    role = data["role"]
    valid_roles = ("system", "user", "assistant", "tool")
    if role not in valid_roles:
        raise ValueError(
            f"Invalid role '{role}'. Must be one of: {', '.join(valid_roles)}"
        )
    
    # Validate content presence
    if "content" not in data:
        raise ValueError("Message must have a 'content' field")
    
    raw_content = data["content"]

    # Normalize content:
    # - if it's a list (e.g. OpenAI content parts), flatten to text
    # - otherwise, coerce to string
    if isinstance(raw_content, list):
        parts: list[str] = []
        for part in raw_content:
            # Typical shape from OpenAI: {"type": "text", "text": "..."}
            if isinstance(part, dict) and part.get("type") == "text":
                parts.append(str(part.get("text", "")))
            else:
                parts.append(str(part))
        normalized_content = "\n".join(parts)
    else:
        normalized_content = str(raw_content)
    
    # Build normalized message
    normalized: dict = {
        "role": role,
        "content": normalized_content,
    }
    
    # Add optional fields if present
    if "tool_call_id" in data and data["tool_call_id"] is not None:
        normalized["tool_call_id"] = str(data["tool_call_id"])
    
    if "name" in data and data["name"] is not None:
        normalized["name"] = str(data["name"])
    
    return normalized


