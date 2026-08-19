# Seshat MCP Server Dockerfile
# Runs the Seshat HTTP/SSE server exposing tools via MCP protocol

FROM python:3.14-slim

WORKDIR /app

# Install git for vault sync
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy package files
COPY pyproject.toml .

# Install dependencies (including dev for package installation)
RUN pip install --no-cache-dir -e ".[dev]"

# Copy source code
COPY seshat/ ./seshat/

# Create vault directories (will be mounted or synced)
RUN mkdir -p /vault/{01-Fragments,02-Projects,03-References,seixu}

# Set vault root as default
ENV SESHAT_VAULT_ROOT=/vault

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()" || exit 1

# Run MCP server
CMD ["python", "-m", "seshat.mcp.cli", \
     "--vault-root", "/vault", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--git-remote", "${SESHAT_GIT_REMOTE}"]
