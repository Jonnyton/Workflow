FROM python:3.11-slim

# System deps for building native extensions (clingo, igraph, spacy, etc.)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        curl \
        git \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (LTS) for Claude CLI
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

# Install Claude CLI globally
RUN npm install -g @anthropic-ai/claude-code

WORKDIR /app

# Copy dependency metadata first for layer caching
COPY pyproject.toml .

# Install the project in editable mode with API extras
# Copy full source before install since editable mode needs it
COPY fantasy_author/ fantasy_author/
RUN pip install --no-cache-dir -e ".[api]"

# Universe data lives on a Railway persistent volume
VOLUME /data/universe

# Railway injects PORT; default to 8321
ENV PORT=8321

EXPOSE ${PORT}

CMD python -m fantasy_author serve \
    --universe /data/universe \
    --host 0.0.0.0 \
    --port ${PORT}
