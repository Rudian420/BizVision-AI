# ============================================================
# BizVision AI — ML development / training image
# CPU base by default; swap to a CUDA base for GPU training.
# ============================================================
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/model_cache

WORKDIR /app

# System deps for scientific / ML wheels (lightgbm, prophet, etc.).
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential git curl libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

# Default: Jupyter Lab for interactive ML development.
EXPOSE 8888
CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root", "--NotebookApp.token="]
