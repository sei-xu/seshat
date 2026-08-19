# Seshat Deployment Guide

This guide covers deploying Seshat MCP server to production on Render or other platforms.

## Overview

Seshat MCP server is a containerized HTTP service that exposes the 9 core vault tools via MCP protocol, with git synchronization for vault updates.

**Current Status**: Deployment-ready, tested locally.

## Prerequisites

- Render account (or Docker-compatible hosting)
- Git repository for vault clone (upstream)
- API key for server authentication
- 10GB+ disk for vault data (persistent storage)

## Local Development

### Setup

```bash
# Install in editable mode
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Start server locally
python -m seshat.mcp.cli \
  --vault-root ./vault \
  --host localhost \
  --port 8000 \
  --api-key your-dev-key
```

### Testing the Server

```bash
# Health check
curl http://localhost:8000/health

# List tools
curl -H "Authorization: Bearer your-dev-key" http://localhost:8000/tools

# Call a tool
curl -X POST http://localhost:8000/call \
  -H "Authorization: Bearer your-dev-key" \
  -H "Content-Type: application/json" \
  -d '{"tool": "list_projects", "params": {}}'
```

## Docker Deployment

### Build Docker Image

```bash
docker build -t seshat:latest .
```

### Run Docker Container

```bash
docker run \
  -p 8000:8000 \
  -v vault-data:/var/data/vault \
  -e SESHAT_API_KEY=your-secure-key \
  -e AKASHA_GIT_REMOTE=https://github.com/username/vault.git \
  seshat:latest
```

## Render Deployment

### Setup Steps

1. **Create Render Account**
   - Sign up at https://render.com

2. **Connect GitHub Repository**
   - Link your Seshat repository to Render
   - Grant necessary permissions

3. **Configure Environment Variables**
   - Go to Service → Settings → Environment
   - Add the following variables:
     - `SESHAT_API_KEY`: Generate with `openssl rand -hex 32`
     - `AKASHA_GIT_REMOTE`: URL to vault repository

4. **Configure Persistent Disk**
   - Service → Disks
   - Add disk: `vault-data` → `/var/data/vault` → 10 GB

5. **Deploy**
   - Render automatically deploys on git push
   - Watch deployment logs at Service → Logs

### Environment Variables on Render

| Variable | Value | Notes |
|----------|-------|-------|
| `SESHAT_API_KEY` | `<generate>` | Create secure random key |
| `AKASHA_GIT_REMOTE` | `https://github.com/.../vault.git` | Upstream vault repo |
| `SESHAT_VAULT_ROOT` | `/var/data/vault` | Persistent disk path |

### Accessing the Server

```bash
# Health check
curl https://your-service.render.com/health

# Call tools
curl -X POST https://your-service.render.com/call \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"tool": "list_projects"}'
```

## Git Synchronization

The server integrates with git for vault updates:

### Initial Setup

```bash
# On the server (Render):
# The server automatically initializes git and adds the remote on startup

# Local testing:
AKASHA_GIT_REMOTE=https://github.com/username/vault.git \
  python -m seshat.mcp.cli --vault-root ./vault
```

### Git Operations via API

```bash
# Check git status
curl https://your-service.render.com/git/status \
  -H "Authorization: Bearer $API_KEY"

# Pull changes from remote
curl -X POST https://your-service.render.com/git/pull \
  -H "Authorization: Bearer $API_KEY"

# Push commits to remote
curl -X POST https://your-service.render.com/git/push \
  -H "Authorization: Bearer $API_KEY"

# View recent commits
curl "https://your-service.render.com/git/log?max=10" \
  -H "Authorization: Bearer $API_KEY"
```

## Troubleshooting

### Server won't start

1. Check environment variables are set:
   ```bash
   echo $SESHAT_API_KEY
   echo $AKASHA_GIT_REMOTE
   ```

2. View logs on Render:
   - Service → Logs tab
   - Look for Python errors or git failures

### Git sync fails

1. Verify git remote is accessible:
   ```bash
   git clone $AKASHA_GIT_REMOTE test-clone
   ```

2. Check git credentials (if private repo):
   - Add SSH key or use HTTPS token in URL
   - `https://token@github.com/user/repo.git`

3. View git error via API:
   ```bash
   curl https://your-service.render.com/git/status \
     -H "Authorization: Bearer $API_KEY"
   ```

### Disk full

1. Check disk usage:
   - Render dashboard → Service → Disks
   - Monitor growth of `/var/data/vault`

2. Clean up:
   - Old history files can be archived
   - Remove test fragments/references

## API Reference

### Tool Calls

**POST /call**

```json
{
  "tool": "list_projects",
  "params": {
    "field": "Programação",
    "project_status": "in_progress"
  }
}
```

Response:
```json
{
  "result": [...],
  "tool": "list_projects"
}
```

### Git Operations

**GET /health** - Server health check

**GET /tools** - List available tools

**GET /git/status** - Current git state

**POST /git/pull** - Fetch and merge from remote

**POST /git/push** - Push commits to remote

**GET /git/log?max=10** - Recent commits

## Monitoring & Maintenance

### Health Checks

Render automatically monitors the `/health` endpoint every 30 seconds.

### Logging

- Render provides real-time logs in the dashboard
- Logs are retained for 7 days (configurable)

### Updates

1. Push changes to main branch
2. Render redeploys automatically (if autoDeploy enabled)
3. Check Logs tab for deployment status

## Security Considerations

1. **API Key**
   - Use strong, randomly generated key
   - Store in Render Secrets, not in code
   - Rotate periodically

2. **Git Remote**
   - Use private repository or token authentication
   - Never commit credentials in code

3. **Network**
   - Render provides HTTPS by default
   - Use only authenticated endpoints for sensitive operations

4. **Disk Access**
   - Only the container can access vault disk
   - Render manages encryption at rest

## Next Steps

1. Test locally with docker
2. Create Render account and link repository
3. Configure environment variables
4. Deploy and verify server is running
5. Connect Claude to the MCP server (see CLAUDE.md)
