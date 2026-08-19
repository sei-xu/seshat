# Seshat Deployment Guide

This guide covers deploying Seshat to production on Render or other platforms.

## Overview

`render.yaml` deploys `seshat.combined.cli` — a single web service running both
the MCP HTTP/SSE server and the Telegram bot, sharing one vault. This fits
Render's **free tier**, which has no persistent disk: on every boot the vault
is cloned fresh from `AKASHA_GIT_REMOTE`, and every write (from either the MCP
server or the bot) is committed and pushed back immediately — git is the only
persistence layer. See "Git Synchronization" below for what that means in
practice (mainly: `AKASHA_GIT_REMOTE` is not optional here).

If you have a paid Render plan with a persistent disk, you can still attach
one at the combined service's `--vault-root` path (or run the MCP server and
bot as separate services, each with `seshat-server`/`seshat-telegram` and its
own disk) — git sync still works there, just as an on-boot refresh + safety
net rather than the sole source of truth.

**Current Status**: Deployment-ready, tested locally.

## Prerequisites

- Render account (or Docker-compatible hosting)
- Git repository for vault clone (upstream) — **required** on Render's free tier
- API key for MCP server authentication (optional but recommended)
- A Telegram bot token (from [@BotFather](https://t.me/BotFather)) and the allowed Telegram user id(s)

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
# No persistent disk — vault lives in git, cloned fresh into /vault on boot
docker run \
  -p 8000:8000 \
  -e SESHAT_API_KEY=your-secure-key \
  -e AKASHA_GIT_REMOTE=https://github.com/username/vault.git \
  -e SESHAT_TELEGRAM_TOKEN=your-bot-token \
  -e SESHAT_TELEGRAM_ALLOWED_USERS=111111,222222 \
  seshat:latest

# Or with a persistent volume, if you have one:
docker run \
  -p 8000:8000 \
  -v vault-data:/vault \
  -e AKASHA_GIT_REMOTE=https://github.com/username/vault.git \
  -e SESHAT_TELEGRAM_TOKEN=your-bot-token \
  -e SESHAT_TELEGRAM_ALLOWED_USERS=111111,222222 \
  seshat:latest
```

## Render Deployment

### Setup Steps (free tier, `render.yaml`, no persistent disk)

1. **Create Render Account**
   - Sign up at https://render.com

2. **Connect GitHub Repository**
   - Link your Seshat repository to Render (it picks up `render.yaml` automatically)
   - Grant necessary permissions

3. **Configure Environment Variables**
   - Go to Service → Settings → Environment
   - Add the following variables:
     - `AKASHA_GIT_REMOTE`: URL to the vault repository (already containing `01-Fragments/`, `02-Projects/`, `03-References/`, `seixu/`) — **required**, this is where the vault is cloned from on every boot
     - `SESHAT_API_KEY`: Generate with `openssl rand -hex 32` (optional — disables MCP auth if unset)
     - `SESHAT_TELEGRAM_TOKEN`: bot token from [@BotFather](https://t.me/BotFather)
     - `SESHAT_TELEGRAM_ALLOWED_USERS`: comma-separated Telegram user ids allowed to use the bot

4. **Deploy**
   - Render automatically deploys on git push
   - Watch deployment logs at Service → Logs — you should see "Starting Seshat combined service..." followed by a successful git clone

### Environment Variables on Render

| Variable | Value | Notes |
|----------|-------|-------|
| `AKASHA_GIT_REMOTE` | `https://github.com/.../vault.git` | Upstream vault repo — required on the free tier |
| `SESHAT_API_KEY` | `<generate>` | Create secure random key (optional) |
| `SESHAT_TELEGRAM_TOKEN` | `<from BotFather>` | Bot token |
| `SESHAT_TELEGRAM_ALLOWED_USERS` | `111111,222222` | Telegram user ids allowed to use the bot |

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

The Telegram bot doesn't expose an HTTP endpoint — talk to it directly on Telegram.

### Free tier caveat: the service sleeps

Render's free web services spin down after ~15 minutes of no HTTP traffic, and
`/health` pings from Render's own monitor don't count as traffic that keeps it
awake either. While asleep, the Telegram bot's long-polling loop is paused —
messages sent to the bot during that window aren't answered until the next
request wakes the service back up (typically the next inbound Telegram
message itself, after a ~30-60s cold start). If you need the bot always
responsive, either upgrade to a paid Render plan (no sleep) or point an
external uptime pinger (e.g. UptimeRobot, cron-job.org) at `/health` on an
interval under 15 minutes.

## Git Synchronization

Both the MCP server and the Telegram bot use `AKASHA_GIT_REMOTE` for vault
persistence, via `seshat.core.git_sync.ensure_synced`:

- **On boot**: if the vault directory is empty, it's `git clone`d from
  `AKASHA_GIT_REMOTE` (branch `main`); if it's already a git repo (persistent
  disk case), it's `git pull`ed instead — a failed pull here just logs a
  warning and continues with whatever's already on disk, so a transient
  network hiccup doesn't crash a working deployment.
- **After every write** (any tool call that changes the vault, from either
  the MCP server or a Telegram write command), the change is committed and
  pushed back to `AKASHA_GIT_REMOTE` immediately. A push failure is logged
  but doesn't turn the write into an error response to the caller — the
  change is still on disk, just not yet synced upstream.

This means on the free tier (no persistent disk) `AKASHA_GIT_REMOTE` isn't
optional — without it the vault starts empty on every boot and nothing
written survives a restart.

### Local Testing

```bash
AKASHA_GIT_REMOTE=https://github.com/username/vault.git \
  python -m seshat.mcp.cli --vault-root ./vault

AKASHA_GIT_REMOTE=https://github.com/username/vault.git \
  python -m seshat.telegram.cli --vault-root ./vault

# Or both together, as Render runs them:
AKASHA_GIT_REMOTE=https://github.com/username/vault.git \
  python -m seshat.combined.cli --vault-root ./vault
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

### Disk full (paid plan with a persistent disk only)

1. Check disk usage:
   - Render dashboard → Service → Disks
   - Monitor growth of your vault-data mount

2. Clean up:
   - Old history files can be archived
   - Remove test fragments/references

On the free tier there's no persistent disk to fill — the vault lives in
`AKASHA_GIT_REMOTE`, so growth is bounded by that repo, not container disk.

### Telegram bot not responding

1. Check the service is awake — see "Free tier caveat" above; a sleeping
   free-tier service needs one request to wake up before it processes queued
   Telegram updates.
2. Verify `SESHAT_TELEGRAM_TOKEN` and `SESHAT_TELEGRAM_ALLOWED_USERS` are set
   correctly — Service → Logs should show "Starting Seshat combined service"
   with the allowed user ids listed.
3. Confirm your Telegram user id is actually in `SESHAT_TELEGRAM_ALLOWED_USERS`
   — an unauthorized sender gets a reply saying so, not silence.

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
