"""Streamlit frontend for DevAgent."""

import sys
from pathlib import Path

# Ensure project root is on sys.path so `import rusty_2...` works
PROJECT_ROOT = Path(__file__).resolve().parents[2]  # .../devops_llm
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import json
from pathlib import Path as _Path

import requests
import streamlit as st
import base64

from rusty_2.common.conversation import Conversation
from rusty_2.frontend.streamlit_display import StreamlitConversationDisplay


# Page configuration
st.set_page_config(
    page_title="Rusty 2.0",
    page_icon="rusty_2/frontend/images/rusty_logo.png",
    layout="wide",
)

# Title
img_bytes = Path("rusty_2/frontend/images/rusty_title.png").read_bytes()
encoded = base64.b64encode(img_bytes).decode()

st.markdown(
    f"""
    <div style="text-align: center;">
        <img src="data:image/png;base64,{encoded}">
    </div>
    """,
    unsafe_allow_html=True,
)

st.header("Rusty 2.0 - Local Autonomous Development Assistant", text_alignment="center")

# Sidebar for configuration
with st.sidebar:
    st.header("Configuration")
    
    repo_root = st.text_input(
        "Repo root path",
        value=str(Path.cwd()),
        help="Path to the repository root directory",
    )
    
    git_mcp_url = st.text_input(
        "Git MCP URL",
        value=f"stdio://python:-m:mcp_server_git:--repository:{repo_root}",
        help="MCP Git server stdio URL (used by the agent to talk to mcp-server-git)",
    )

    
    max_steps = st.number_input(
        "Max steps",
        min_value=1,
        max_value=100,
        value=20,
        help="Maximum number of agent iterations",
    )

# Initialize conversation history in session state
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []
if "repo_config" not in st.session_state:
    st.session_state.repo_config = {}
if "chat_input_counter" not in st.session_state:
    st.session_state.chat_input_counter = 0

# Main panel - Chat interface
st.subheader("Chat with Rusty")

# Display conversation history
if st.session_state.conversation_history:
    st.markdown("### Conversation History")
    for msg in st.session_state.conversation_history:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        
        if role == "system":
            # System messages are typically hidden or shown in a muted style
            with st.expander("System Message", expanded=False):
                st.markdown(content)
        elif role == "user":
            st.markdown(
                f'<div style="padding: 10px; background-color: #007bff; color: white; '
                f'border-radius: 10px; margin: 10px 0; text-align: right; margin-left: 20%;">'
                f'<strong>You</strong><br>{content}</div>',
                unsafe_allow_html=True,
            )
        elif role == "assistant":
            # Display assistant message with avatar
            col_avatar, col_msg = st.columns([1, 20])
            with col_avatar:
                st.image("rusty_2/frontend/images/rusty_logo.png", width=50)
            with col_msg:
                st.markdown(
                    f'<div style="padding: 10px; background-color: #e9ecef; border-left: 4px solid #28a745; '
                    f'border-radius: 10px; margin: 10px 0; margin-right: 20%;">'
                    f'<strong>Rusty</strong><br>{content}</div>',
                    unsafe_allow_html=True,
                )
        elif role == "tool":
            tool_call_id = msg.get("tool_call_id", "")
            tool_id_text = f" (ID: {tool_call_id})" if tool_call_id else ""
            st.markdown(f"**Tool Output{tool_id_text}**")
            st.code(content, language=None)

# Display execution summary if available
if "last_execution_summary" in st.session_state and st.session_state.last_execution_summary:
    st.markdown("### Execution Summary")
    summary = st.session_state.last_execution_summary
    col1, col2, col3 = st.columns(3)
    
    with col1:
        status_emoji = "✅" if summary["success"] else "❌"
        st.metric("Status", f"{status_emoji} {'Success' if summary['success'] else 'Failed'}")
    
    with col2:
        st.metric("Steps", summary["steps"])
    
    with col3:
        if summary["error"]:
            st.error(f"Error: {summary['error']}")
        else:
            st.success("No errors")

# Chat input - use counter in key to allow clearing
task_description = st.text_area(
    "Type your message:",
    placeholder="e.g., Fix the bug in the authentication module...",
    key=f"chat_input_{st.session_state.chat_input_counter}",
    height=150
)

# Buttons
col1, col2 = st.columns([1, 1])
with col1:
    send_button = st.button("Send Message", type="primary", use_container_width=True)
with col2:
    clear_button = st.button("Clear Conversation", use_container_width=True)

# Handle clear conversation
if clear_button:
    st.session_state.conversation_history = []
    st.session_state.repo_config = {}
    if "last_execution_summary" in st.session_state:
        del st.session_state.last_execution_summary
    st.session_state.chat_input_counter += 1  # Clear input field
    st.rerun()

# Handle send message
if send_button:
    if not task_description.strip():
        st.error("Please enter a message.")
    elif not repo_root.strip():
        st.error("Please enter a repository root path.")
    elif not git_mcp_url.strip():
        st.error("Please enter a Git MCP URL.")
    else:
        # Store repo config in session state (for consistency across messages)
        if not st.session_state.repo_config:
            st.session_state.repo_config = {
                "repo_root": repo_root,
                "git_mcp_url": git_mcp_url,
                "max_steps": max_steps,
            }
        else:
            # Update config if changed
            st.session_state.repo_config.update({
                "repo_root": repo_root,
                "git_mcp_url": git_mcp_url,
                "max_steps": max_steps,
            })
        
        # Prepare conversation history for API (exclude the new user message we're about to send)
        # Format messages to match MessageModel structure
        conversation_history_for_api = None
        if st.session_state.conversation_history:
            conversation_history_for_api = []
            for msg in st.session_state.conversation_history:
                msg_dict = {
                    "role": msg.get("role", "unknown"),
                    "content": msg.get("content", ""),
                }
                if msg.get("tool_call_id"):
                    msg_dict["tool_call_id"] = msg["tool_call_id"]
                conversation_history_for_api.append(msg_dict)
        
        # Add user message to conversation history (for display)
        st.session_state.conversation_history.append({
            "role": "user",
            "content": task_description,
        })
        
        # Show loading spinner
        with st.spinner("Rusty is thinking..."):
            try:
                # Prepare request payload
                payload = {
                    "task_description": task_description,
                    "repo_root": st.session_state.repo_config["repo_root"],
                    "git_mcp_url": st.session_state.repo_config["git_mcp_url"],
                    "max_steps": st.session_state.repo_config["max_steps"],
                    "conversation_history": conversation_history_for_api,
                }
                
                # Determine API URL (try to get from session state or use default)
                api_url = st.session_state.get("api_url", "http://localhost:8000")
                endpoint = f"{api_url}/dev-agent/run"
                
                # Call FastAPI backend
                response = requests.post(
                    endpoint,
                    json=payload,
                    timeout=300,  # 5 minute timeout for long-running tasks
                )
                
                # Check response status
                response.raise_for_status()
                
                # Parse JSON response
                result = response.json()
                
                # Extract data
                success = result.get("success", False)
                steps = result.get("steps", 0)
                error = result.get("error")
                messages = result.get("messages", [])
                
                # Update conversation history with all messages from the response
                # (this includes the new user message and all assistant/tool responses)
                st.session_state.conversation_history = []
                for msg in messages:
                    msg_dict = {
                        "role": msg.get("role", "unknown"),
                        "content": msg.get("content", ""),
                    }
                    if msg.get("tool_call_id"):
                        msg_dict["tool_call_id"] = msg["tool_call_id"]
                    st.session_state.conversation_history.append(msg_dict)
                
                # Store execution summary in session state for persistent display
                st.session_state.last_execution_summary = {
                    "success": success,
                    "steps": steps,
                    "error": error,
                }
                
                # Increment counter to clear the input field (creates new widget instance)
                st.session_state.chat_input_counter += 1
                
                # Rerun to show updated conversation
                st.rerun()
                
            except requests.exceptions.RequestException as e:
                st.error(f"Error connecting to API: {str(e)}")
                st.info(
                    "Make sure the FastAPI backend is running. "
                    "You can start it with: `uvicorn rusty_2.backend.api:app --reload`"
                )
            except json.JSONDecodeError as e:
                st.error(f"Error parsing API response: {str(e)}")
            except Exception as e:
                st.error(f"Unexpected error: {str(e)}")

# API URL configuration in sidebar
with st.sidebar:
    st.divider()
    st.header("API Settings")
    api_url = st.text_input(
        "API URL",
        value=st.session_state.get("api_url", "http://localhost:8000"),
        help="Base URL of the FastAPI backend",
    )
    st.session_state["api_url"] = api_url

# Instructions
with st.expander("ℹ️ How to use"):
    st.markdown("""
    1. **Configure the settings** in the sidebar:
       - Enter the repository root path
       - Enter the Git MCP server URL
       - Set the maximum number of steps
    
    2. **Type your message** in the chat input field
    
    3. **Click "Send Message"** to send it to Rusty
    
    4. **Continue the conversation** by sending additional messages
    
    5. **Clear the conversation** using the "Clear Conversation" button to start fresh
    
    **Note**: Make sure the FastAPI backend is running before starting a task.
    """)

