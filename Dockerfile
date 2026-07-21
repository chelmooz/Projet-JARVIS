
# syntax=docker/dockerfile:1

FROM python:3.11-slim AS base

# Évite les prompts interactifs et optimise les logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Installation des dépendances système minimales (si compilation nécessaire)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Installation des dépendances Python (couche mise en cache)
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copie du code source
COPY . .

# Exposition du port API
EXPOSE 8000

# Commande de démarrage (plus de launcher.py complexe)
CMD ["uvicorn", "jarvis:app", "--host", "0.0.0.0", "--port", "8000"]
