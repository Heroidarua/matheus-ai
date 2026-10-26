FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl unzip \
    && curl -fsSL https://github.com/projectdiscovery/nuclei/releases/download/v3.11.1/nuclei_3.11.1_linux_amd64.zip -o /tmp/nuclei.zip \
    && unzip -q /tmp/nuclei.zip nuclei -d /usr/local/bin \
    && chmod 0755 /usr/local/bin/nuclei \
    && rm -f /tmp/nuclei.zip \
    && apt-get purge -y --auto-remove curl unzip \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY static ./static

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
