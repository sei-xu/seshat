# Seshat combined service Dockerfile
# Runs the MCP HTTP/SSE server and the Telegram bot in one process, sharing
# one vault clone (see seshat/combined/cli.py). Set AKASHA_GIT_REMOTE to sync
# the vault via git — required if /vault isn't a persistent volume.

FROM python:3.14-slim

WORKDIR /app

# Install git for vault sync
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy package files
COPY pyproject.toml .

# Install dependencies (including dev/telegram extras for package installation)
RUN pip install --no-cache-dir -e ".[dev,telegram]"

# Copy source code
COPY seshat/ ./seshat/

# Create vault directories (used when AKASHA_GIT_REMOTE is unset — otherwise
# seshat.combined.cli clones over this on boot)
RUN mkdir -p /vault/{01-Fragments,02-Projects,03-References,seixu}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()" || exit 1

# Run the combined MCP server + Telegram bot service
CMD ["python", "-m", "seshat.combined.cli", \
     "--vault-root", "/vault", \
     "--host", "0.0.0.0", \
     "--port", "8000"]
