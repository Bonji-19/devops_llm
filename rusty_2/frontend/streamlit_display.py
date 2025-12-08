"""Streamlit components for displaying conversations."""

from typing import Union

import streamlit as st

from rusty_2.common.conversation import Conversation



class StreamlitConversationDisplay:
    """
    Renders a conversation in Streamlit with role-based styling.
    
    This class provides a simple way to display conversations in a chat-like
    layout, with different visual styles for system, user, assistant, and tool messages.
    """
    
    def __init__(self, conversation: Union[Conversation, list[dict]]):
        """
        Initialize the conversation display.
        
        Args:
            conversation: Either a Conversation object or a list of message dictionaries
        """
        if isinstance(conversation, Conversation):
            self.messages = conversation.messages
        else:
            self.messages = conversation
    
    def render(self) -> None:
        """
        Render the conversation in Streamlit.
        
        Messages are displayed with role-specific styling:
        - System messages: Muted style with info icon
        - User messages: Right-aligned with user styling
        - Assistant messages: Left-aligned with assistant styling
        - Tool messages: Monospace code blocks in boxes
        """
        for msg in self.messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            
            if role == "system":
                self._render_system_message(content)
            elif role == "user":
                self._render_user_message(content)
            elif role == "assistant":
                self._render_assistant_message(content)
            elif role == "tool":
                self._render_tool_message(content, msg.get("tool_call_id"))
            else:
                # Fallback for unknown roles
                st.markdown(f"**{role}**: {content}")
    
    def _render_system_message(self, content: str) -> None:
        """Render a system message in muted style."""
        st.markdown(
            f'<div style="padding: 10px; background-color: #f0f2f6; border-left: 4px solid #1f77b4; '
            f'border-radius: 5px; margin: 10px 0; color: #666;">'
            f'<strong>System</strong><br>{content}</div>',
            unsafe_allow_html=True,
        )
    
    def _render_user_message(self, content: str) -> None:
        """Render a user message on the right side."""
        st.markdown(
            f'<div style="padding: 10px; background-color: #007bff; color: white; '
            f'border-radius: 10px; margin: 10px 0; text-align: right; margin-left: 20%;">'
            f'<strong>You</strong><br>{content}</div>',
            unsafe_allow_html=True,
        )
    
    def _render_assistant_message(self, content: str) -> None:
        """Render an assistant message on the left side."""
        st.markdown(
            f'<div style="padding: 10px; background-color: #e9ecef; border-left: 4px solid #28a745; '
            f'border-radius: 10px; margin: 10px 0; margin-right: 20%;">'
            f'<strong>Assistant</strong><br>{content}</div>',
            unsafe_allow_html=True,
        )
    
    def _render_tool_message(self, content: str, tool_call_id: str | None = None) -> None:
        """Render a tool message in a monospace code block style."""
        tool_id_text = f" (ID: {tool_call_id})" if tool_call_id else ""
        st.markdown(f"**Tool Output{tool_id_text}**")
        st.code(content, language=None)

