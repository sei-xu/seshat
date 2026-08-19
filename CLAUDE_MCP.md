# Connecting Claude to Seshat MCP Server

This guide explains how to connect Claude Code (or any Claude integration) to the Seshat MCP server so Claude can access all vault tools.

## Overview

Once connected, Claude will have access to:
- **list_projects** — List vault projects with filtering
- **get_project** — Retrieve project details and history
- **create_project** — Create new projects
- **append_history** — Add timeline entries to projects
- **create_fragment** — Create short notes/fragments
- **list_references** — List reference entries
- **create_reference** — Create new references
- **update_project_status** — Change project state
- **search_vault** — Search vault content

## Local Setup (Claude Code CLI or IDE Extension)

### Option 1: Local HTTP Server (Recommended for Development)

1. **Start Seshat Server Locally**

   ```bash
   # In the seshat repo directory
   pip install -e ".[dev]"
   
   # Start server with local vault
   export SESHAT_API_KEY="your-dev-key"
   python -m seshat.mcp.cli \
     --vault-root ./vault \
     --host localhost \
     --port 8000
   ```

2. **Configure Claude Code MCP**

   Create `~/.claude/settings.json` (or update existing):

   ```json
   {
     "mcpServers": {
       "seshat-local": {
         "command": "curl",
         "args": [],
         "env": {},
         "disabled": false
       }
     }
   }
   ```

   Or use `.claude/mcp.json` in the project:

   ```json
   {
     "mcpServers": {
       "seshat": {
         "command": "python",
         "args": ["-m", "seshat.mcp.cli"],
         "env": {
           "SESHAT_VAULT_ROOT": "${workspaceFolder}/vault",
           "SESHAT_API_KEY": "your-dev-key"
         }
       }
     }
   }
   ```

3. **Start Claude Code**

   ```bash
   claude code
   # Or via IDE: use the MCP server configuration
   ```

4. **Test Connection**

   In Claude Code, try using a Seshat tool:

   ```
   @seshat list_projects
   
   or

   Use the "list_projects" tool to show me all projects
   ```

### Option 2: Remote Seshat Server (Production)

For a deployed Seshat server on Render or other cloud platform:

1. **Get Server URL and API Key**

   ```
   Server URL: https://your-seshat.render.com
   API Key: (from Render environment variables)
   ```

2. **Create Custom MCP Wrapper**

   Since Claude Code's native MCP might not directly support remote HTTP servers, you can create a local wrapper script:

   Create `./seshat-mcp-client.py`:

   ```python
   #!/usr/bin/env python3
   import json
   import sys
   import os
   import urllib.request
   import urllib.error

   SERVER_URL = os.getenv("SESHAT_SERVER_URL", "http://localhost:8000")
   API_KEY = os.getenv("SESHAT_API_KEY")

   def call_tool(tool_name: str, params: dict) -> dict:
       url = f"{SERVER_URL}/call"
       headers = {
           "Content-Type": "application/json",
       }
       if API_KEY:
           headers["Authorization"] = f"Bearer {API_KEY}"

       payload = json.dumps({"tool": tool_name, "params": params})
       request = urllib.request.Request(
           url, data=payload.encode(), headers=headers, method="POST"
       )
       try:
           with urllib.request.urlopen(request) as response:
               return json.loads(response.read())
       except urllib.error.HTTPError as e:
           return {"error": str(e)}

   # Read command from argv or stdin
   if len(sys.argv) > 1:
       tool_name = sys.argv[1]
       params = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
   else:
       line = json.loads(sys.stdin.read())
       tool_name = line.get("tool")
       params = line.get("params", {})

   result = call_tool(tool_name, params)
   print(json.dumps(result))
   ```

   Configure in `.claude/mcp.json`:

   ```json
   {
     "mcpServers": {
       "seshat-remote": {
         "command": "python",
         "args": ["./seshat-mcp-client.py"],
         "env": {
           "SESHAT_SERVER_URL": "https://your-seshat.render.com",
           "SESHAT_API_KEY": "${env:SESHAT_API_KEY}"
         }
       }
     }
   }
   ```

## Using Seshat Tools from Claude

### Example 1: List Projects

```
Can you list all my projects in the Programação field that are in progress?

Claude will call: list_projects(field="Programação", project_status="in_progress")
```

### Example 2: Create a Project

```
Create a new project for a web design client called "WebFlow", it's a commercial project in the Design field. Set the summary as "Client website redesign".

Claude will call: create_project(
  year_month="202608",
  slug="webflow",
  title="WebFlow",
  summary="Client website redesign",
  field="Design",
  project_type="comercial"
)
```

### Example 3: Add History Entry

```
Add a history entry to my 202608_webflow project: "2026-08-20, Kickoff call with client, Design kickoff with full team"

Claude will call: append_history(
  history_relative_path="02-Projects/202608_webflow/01_history.md",
  date="2026-08-20",
  title="Kickoff call with client",
  summary_line="Design kickoff with full team"
)
```

### Example 4: Search Vault

```
Search for all notes about "responsive design" in the Design field

Claude will call: search_vault(
  query="responsive design",
  field="Design"
)
```

## Environment Setup

### Required Variables

For local development:
```bash
export SESHAT_API_KEY="your-dev-key-123"
export SESHAT_VAULT_ROOT="./vault"
```

For remote server:
```bash
export SESHAT_SERVER_URL="https://your-seshat.render.com"
export SESHAT_API_KEY="your-production-key"
```

### Optional Variables

```bash
export SESHAT_HOST="127.0.0.1"      # MCP server host
export SESHAT_PORT="8000"           # MCP server port
export SESHAT_GIT_REMOTE="https://..." # Git repo for sync
```

## Troubleshooting

### "Tool not found" Error

1. Verify Seshat server is running:
   ```bash
   curl http://localhost:8000/health
   ```

2. Check MCP configuration:
   - `.claude/mcp.json` file exists
   - Server URL/command is correct
   - Environment variables are set

3. Restart Claude Code and server

### "Unauthorized" Error (401)

1. Verify API key is set:
   ```bash
   echo $SESHAT_API_KEY
   ```

2. Check that MCP config passes API key:
   ```json
   "env": {
     "SESHAT_API_KEY": "${env:SESHAT_API_KEY}"
   }
   ```

3. Generate new API key if needed:
   ```bash
   openssl rand -hex 32
   ```

### Server Connection Failed

1. Check server is running:
   ```bash
   python -m seshat.mcp.cli --vault-root ./vault
   ```

2. Verify firewall/network:
   ```bash
   curl -v http://localhost:8000/health
   ```

3. Check logs for errors

### Tool Calls Timeout

1. Vault might be large, check performance:
   ```bash
   curl http://localhost:8000/git/status
   ```

2. For remote server, check network latency

3. Increase timeout in MCP client if supported

## Advanced: Custom Tool Wrapper

For specialized use cases, create a custom MCP wrapper that adds features:

```python
# seshat-enhanced.py
import json
import sys
from seshat.core import VaultClient
from seshat.core.tools import *

vault = VaultClient("./vault")

def handle_command(cmd: dict):
    tool = cmd.get("tool")
    params = cmd.get("params", {})
    
    if tool == "list_projects":
        results = list_projects(vault, **params)
        # Custom processing here
        return {"result": results}
    
    # ... handle other tools

if __name__ == "__main__":
    cmd = json.loads(sys.stdin.read())
    result = handle_command(cmd)
    print(json.dumps(result))
```

Then reference in `.claude/mcp.json`:

```json
{
  "mcpServers": {
    "seshat": {
      "command": "python",
      "args": ["./seshat-enhanced.py"],
      "env": { "SESHAT_VAULT_ROOT": "./vault" }
    }
  }
}
```

## Next Steps

1. Start local Seshat server
2. Configure Claude Code MCP
3. Test tool calls with Claude
4. Create workflow for regular use

For production deployment, see [DEPLOYMENT.md](DEPLOYMENT.md)
