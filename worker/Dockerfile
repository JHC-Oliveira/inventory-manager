FROM python:3.12-slim-bookworm

RUN useradd --create-home workeruser

WORKDIR /app

RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
COPY requirements-dev.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements-dev.txt

COPY . .

RUN chown -R workeruser:workeruser /app

USER workeruser

CMD ["python", "main.py"]