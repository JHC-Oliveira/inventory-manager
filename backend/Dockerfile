# Base image: python:3.12-slim-bookworm
# OS-level CVEs: Some Debian-level vulnerabilities are reported by Docker Scout.
# All fixable Python package vulnerabilities are resolved via pip-audit.
# Remaining OS CVEs have no available fix in Debian Bookworm at this time.
# Rebuild regularly to pick up new Debian security patches.
FROM python:3.12-slim-bookworm

# Security: create a non-root user to run the app
RUN useradd --create-home appuser

# Set the working directory inside the container
WORKDIR /app

RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (before the rest of the code)
# This is a Docker caching trick explained below
COPY requirements.txt .
COPY requirements-dev.txt .

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements-dev.txt
    
# Copy the rest of the application code
COPY . .

# Switch from root to our non-root user
USER appuser

# Tell Docker this container listens on port 8000
EXPOSE 8000

# The command that runs when the container starts
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]