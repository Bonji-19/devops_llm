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

from rusty_2.common.conversation import Conversation
from rusty_2.frontend.streamlit_display import StreamlitConversationDisplay


# Page configuration
st.set_page_config(
    page_title="Rusty 2.0",
    page_icon="rusty_2/frontend/images/rusty_logo.png",
    layout="wide",
)

# Title
st.image("rusty_2/frontend/images/rusty_title.png")
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

# Main panel
st.subheader("Task Description")

task_description = st.text_area(
    "Describe the task you want Rusty to perform:",
    height=150,
    placeholder="e.g., Fix the bug in the authentication module...",
)

# Run button
if st.button("Run Rusty", type="primary", use_container_width=True):
    if not task_description.strip():
        st.error("Please enter a task description.")
    elif not repo_root.strip():
        st.error("Please enter a repository root path.")
    elif not git_mcp_url.strip():
        st.error("Please enter a Git MCP URL.")
    else:
        # Show loading spinner
        with st.spinner("Rusty is thinking..."):
            try:
                # Prepare request payload
                payload = {
                    "task_description": task_description,
                    "repo_root": repo_root,
                    "git_mcp_url": git_mcp_url,
                    "max_steps": max_steps,
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
                
                # Display summary
                st.header("Execution Summary")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    status_emoji = "✅" if success else "❌"
                    st.metric("Status", f"{status_emoji} {'Success' if success else 'Failed'}")
                
                with col2:
                    st.metric("Steps", steps)
                
                with col3:
                    if error:
                        st.error(f"Error: {error}")
                    else:
                        st.success("No errors")
                
                # Convert messages to conversation format
                message_dicts = []
                for msg in messages:
                    msg_dict = {
                        "role": msg.get("role", "unknown"),
                        "content": msg.get("content", ""),
                    }
                    if msg.get("tool_call_id"):
                        msg_dict["tool_call_id"] = msg["tool_call_id"]
                    message_dicts.append(msg_dict)
                
                # Create conversation object
                conversation = Conversation(messages=message_dicts)
                
                # Display conversation
                st.header("Conversation")
                display = StreamlitConversationDisplay(conversation)
                display.render()
                
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
    
    2. **Enter your task description** in the main panel
    
    3. **Click "Run Rusty"** to start the agent
    
    4. **View the results**:
       - Check the execution summary
       - Review the full conversation
    
    **Note**: Make sure the FastAPI backend is running before starting a task.
    """)

