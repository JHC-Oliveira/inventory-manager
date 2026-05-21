FROM python:3.12-slim-bookworm

RUN useradd --create-home workeruser

WORKDIR /app

RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir pip-audit==2.9.0 \
    && pip-audit -r requirements.txt

COPY . .

USER workeruser

CMD ["python", "main.py"]