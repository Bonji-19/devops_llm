# devops_llm

This repository contains an autonomous development assistant (DevAgent) that uses LLMs and MCP tools to perform development tasks.

## Setup

### Prerequisites

- **Miniconda** or **Anaconda** installed ([Download here](https://docs.conda.io/en/latest/miniconda.html))
- **Git** installed
- API keys for either:
  - OpenAI API key (for OpenAI backend)
  - Google API key (for Gemini backend)

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd devops_llm
```

### Step 2: Create Conda Environment

Create and activate the conda environment from `environment.yml`:

```bash
conda env create -f environment.yml -n rusty_2
conda activate rusty_2
```

**Note:** If `mcp-server-git` is not found during environment creation, install it manually:

```bash
pip install mcp-server-git
```

### Step 3: Configure Environment Variables

Create a `.env` file in the repository root (`devops_llm/.env`) with your API keys:

**For OpenAI backend:**
```env
OPENAI_API_KEY=your_openai_api_key_here
LLM_BACKEND_NAME=openai
LLM_MODEL_NAME=gpt-4o-mini
```

**For Gemini backend:**
```env
GOOGLE_API_KEY=your_google_api_key_here
LLM_BACKEND_NAME=gemini
LLM_MODEL_NAME=gemini-pro
```

### Step 4: Start the Backend API

In one terminal, activate the environment and start the FastAPI backend:

```bash
conda activate rusty_2
uvicorn rusty_2.backend.api:app --reload
```

The API will be available at `http://localhost:8000`

### Step 5: Start the Streamlit Frontend

In a **second terminal**, activate the environment and start Streamlit:

```bash
conda activate rusty_2
streamlit run rusty_2/frontend/app.py
```

The Streamlit UI will open in your browser at `http://localhost:8501`

### Step 6: Use the Agent

1. In the Streamlit interface, configure:
   - **Repo root path**: Path to **any** repository you want the agent to work on (e.g., `D:\hslu\git\my_project`)
   - **Git MCP URL**: `stdio://python:-m:mcp_server_git:--repository:<same-repo-path-as-above>`
     - **Important**: The repository path in the Git MCP URL must match the repo root path
   - **Max steps**: Maximum number of agent iterations (default: 20)

2. Enter a task description in the text area

3. Click **"Run Dev Agent"** to execute

**Repository Requirements:**
- The repository must be initialized with Git (have a `.git` directory)
- It can be **local-only** - no remote repository needed
- It can be **private** - the agent works entirely locally
- It can be **uncommitted** - even a fresh `git init` works
- The repository path must exist and be accessible

The agent uses Git commands locally via the MCP server - it never needs network access to GitHub/GitLab/etc.

## Example Tasks

**For exploring repositories:**
- "Use list_files to explore the repository structure starting from the root. Then read the README.md file and summarize what this project does."
- "List all files in the repository, identify the main source code directories, and read key files to understand the project structure."
- "Explore this repository: use list_files to see what folders exist, then read the README and main configuration files to understand the project."

**For specific file operations:**
- "Read the file `src/main.py` and explain what it does."
- "Use read_file to read `rusty_2/backend/dev_agent.py` and explain how the agent loop works."

**For modifications:**
- "Read `config.json`, then use apply_unified_diff to change the version number from 1.0 to 2.0."

**Tip:** If the agent seems to only use Git tools and not explore files, try prompts that explicitly mention "use list_files" or "read the README file" to guide it.

## Project Structure

- `rusty_2/backend/` - FastAPI backend and DevAgent core logic
- `rusty_2/common/` - Shared utilities (LLM client, MCP client, conversation management)
- `rusty_2/frontend/` - Streamlit UI
- `scripts/` - Test and utility scripts
- `rusty_2/backend/eval/` - Evaluation harness for batch testing

## Troubleshooting

- **"conda: command not found"**: Make sure Conda is installed and initialized. Use Anaconda Prompt or run `conda init powershell` and restart your terminal.
- **"No module named mcp_server_git"**: Install with `pip install mcp-server-git` in the activated conda environment.
- **API quota errors**: Check your API key billing/quota, or switch to a different backend (Gemini/OpenAI) in your `.env` file.
- **Backend connection errors**: Ensure the FastAPI backend is running before using Streamlit. 
