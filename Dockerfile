FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for tree-sitter and build tools
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy tree-sitter grammar build script
COPY build_grammars.py .

# Build tree-sitter grammars
RUN python build_grammars.py

# Copy application code and plugins
COPY app/ ./app/
COPY plugins/ ./plugins/

# Change ownership to non-root user
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port for FastAPI
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command for production with uvicorn
# - workers: 4 for production performance
# - log-level: info for production logging
# - access-log: enable access logging
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--log-level", "info", "--access-log"]
