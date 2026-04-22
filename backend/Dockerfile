# Use the official slim Python 3.12 image as our base
FROM python:3.12-slim-bookworm

# Security: create a non-root user to run the app
RUN useradd --create-home appuser

# Set the working directory inside the container
WORKDIR /app

# Copy requirements first (before the rest of the code)
# This is a Docker caching trick explained below
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Switch from root to our non-root user
USER appuser

# Tell Docker this container listens on port 8000
EXPOSE 8000

# The command that runs when the container starts
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]