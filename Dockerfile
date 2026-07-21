# syntax=docker/dockerfile:1
FROM python:3.11-slim AS base

# Variables d'environnement pour un comportement Python propre et sécurisé
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=/app

WORKDIR /app

# Installation des dépendances système minimales (pour les compilations C si besoin)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copie et installation des dépendances Python (couche mise en cache pour des builds rapides)
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copie du code source (exclut les fichiers inutiles via .dockerignore)
COPY . .

# Exposition du port de l'API FastAPI
EXPOSE 8000

# Point d'entrée : on utilise directement uvicorn, plus de launcher.py complexe
CMD ["uvicorn", "controllers.router:app", "--host", "0.0.0.0", "--port", "8000"]
