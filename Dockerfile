FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY schema.sql schema.cypher ./
COPY scripts ./scripts
COPY docker/api-entrypoint.sh /api-entrypoint.sh

RUN mkdir -p /app/data/uploads /cache/huggingface/hub \
    && sed -i 's/\r$//' /api-entrypoint.sh \
    && chmod +x /api-entrypoint.sh

# Root is intentional for local Docker Desktop volume permission quirks.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UPLOAD_DIR=/app/data/uploads \
    HF_HOME=/cache/huggingface \
    TRANSFORMERS_CACHE=/cache/huggingface \
    HUGGINGFACE_HUB_CACHE=/cache/huggingface/hub \
    HF_HUB_CACHE=/cache/huggingface/hub

EXPOSE 8000

# No --reload by default: watchfiles + bge-m3 easily OOM in Docker Desktop.
ENTRYPOINT ["/api-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
