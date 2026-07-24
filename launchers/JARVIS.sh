#!/usr/bin/env bash
# JARVIS Portable Edition v5.4 — Lanceur 100% portable
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

OS="$(uname -s)"
ARCH="$(uname -m)"

echo "==================================================="
echo "  JARVIS Portable Edition v5.4"
echo "  OS : $OS / $ARCH"
echo "==================================================="
echo

# Charger .env si present (surcharge OLLAMA_HOST, JARVIS_PORT...)
if [ -f "$ROOT/.env" ]; then
  set -a
  . "$ROOT/.env"
  set +a
fi

USING_PORTABLE=0

case "$OS" in
  Linux*)
    PLATFORM="linux"
    PY_DIR="$ROOT/portable_python/linux"
    PY_BIN="$PY_DIR/python3"
    OLLAMA_BIN="$ROOT/bin/linux/ollama"
    USING_PORTABLE=1
    ;;
  Darwin*)
    PLATFORM="mac"
    PY_DIR="$ROOT/portable_python/mac"
    PY_BIN="$PY_DIR/bin/python3"
    OLLAMA_BIN="$ROOT/bin/mac/ollama"
    if [ ! -f "$OLLAMA_BIN" ]; then
      OLLAMA_BIN="$(command -v ollama 2>/dev/null)"
    fi
    if [ ! -f "$PY_BIN" ]; then
      PY_BIN="$(command -v python3)"
      if [ -z "$PY_BIN" ]; then
        echo "  [ERREUR] Aucun Python trouve (portable ni systeme)."
        exit 1
      fi
      echo "  [INFO] Python portable introuvable — utilisation de $PY_BIN"
    else
      USING_PORTABLE=1
    fi
    if [ "$ARCH" = "arm64" ]; then
      export OLLAMA_METAL=1
      echo "  [INFO] Apple Silicon — Metal active"
    fi
    ;;
  *)
    echo "  [ERREUR] OS non supporte : $OS"
    exit 1
    ;;
esac

# Verifications
if [ ! -f "$PY_BIN" ]; then
  echo
  echo "  [ERREUR] Python portable introuvable :"
  echo "    $PY_BIN"
  echo
  echo "  La cle USB est corrompue ou incomplete."
  echo "  Re-telechargez le projet depuis la source d origine."
  exit 1
fi

# Detection dynamique de la version Python pour le check stdlib (portable uniquement)
if [ "$USING_PORTABLE" = "1" ]; then
  PY_VERSION=$("$PY_BIN" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "3.13")
  PY_STDLIB="$PY_DIR/lib/python$PY_VERSION"

  if [ ! -d "$PY_STDLIB" ]; then
    echo
    echo "  [ERREUR] Bibliotheque standard Python manquante."
    echo "    Attendu : $PY_STDLIB"
    echo "  La cle USB est corrompue ou incomplete."
    echo "  Re-telechargez le projet depuis la source d origine."
    exit 1
  fi
fi

if [ "$USING_PORTABLE" = "1" ]; then
  export PYTHONHOME="$PY_DIR"
  trap 'unset PYTHONHOME' EXIT
fi

echo "  Python : $PY_BIN"

# L'installation des dependances est deleguee a services.system.ensure_venv()
# dans jarvis.py (source unique, evite la race condition shell vs Python).
# Verification Ollama (non bloquant)
if [ ! -f "$OLLAMA_BIN" ]; then
  echo "  [AVERT] Ollama introuvable : $OLLAMA_BIN"
fi

echo
echo "  Demarrage de JARVIS..."
echo "==================================================="
echo
exec "$PY_BIN" "$ROOT/jarvis.py"
