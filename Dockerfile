FROM python:3.12-slim

# Build ID único para forçar build limpo (muda a cada commit)
ARG BUILD_ID=unknown
ENV BUILD_ID=${BUILD_ID}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# Dependências básicas do container da API. Ferramentas de auditoria devem ser instaladas no executor VPS, não nesta imagem.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ca-certificates \
       python3 python3-pip git curl wget \
       nmap netcat-openbsd sqlmap gobuster jq \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY vendor/pestinha ./vendor/pestinha
COPY static ./static
COPY data ./data

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
