#!/usr/bin/env bash
# run_integration_tests.sh — Lance les tests d'integration avec le Ollama portable
# Usage: ./scripts/run_integration_tests.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OLLAMA_BIN="$ROOT/bin/linux/ollama"
OLLAMA_PORT=11436

echo "=== Integration Tests JARVIS ==="
echo "Ollama : $OLLAMA_BIN"
echo "Port   : $OLLAMA_PORT"

if [ ! -f "$OLLAMA_BIN" ]; then
  echo "ERREUR: Ollama binaire introuvable dans $OLLAMA_BIN"
  echo "Assurez-vous que le binaire est present dans bin/linux/"
  exit 1
fi

# Nettoyer les processus Ollama residuels
pkill -f "ollama serve" 2>/dev/null || true
sleep 1

# Demarrer Ollama
export OLLAMA_HOST="127.0.0.1:$OLLAMA_PORT"
export OLLAMA_MODELS="$ROOT/models/ollama"
mkdir -p "$OLLAMA_MODELS"

echo "Demarrage d'Ollama..."
"$OLLAMA_BIN" serve &
OLLAMA_PID=$!

# Attendre qu'Ollama soit pret
echo "Attente d'Ollama..."
for i in $(seq 1 30); do
  if curl -s "http://$OLLAMA_HOST/api/tags" > /dev/null 2>&1; then
    echo "Ollama pret (tentative $i)"
    break
  fi
  sleep 2
done

if ! kill -0 $OLLAMA_PID 2>/dev/null; then
  echo "ERREUR: Ollama n'a pas demarre"
  exit 1
fi

# Verifier les modeles disponibles
echo "Modeles disponibles:"
curl -s "http://$OLLAMA_HOST/api/tags" | python3 -c "import sys,json; [print(f'  - {m[\"name\"]}') for m in json.load(sys.stdin).get('models',[])]"

# Lancer les tests
echo ""
echo "Execution des tests d'integration..."
cd "$ROOT"
python3 -m pytest tests/test_integration_ollama.py -v --tb=long

EXIT_CODE=$?

# Nettoyage
echo ""
echo "Arret d'Ollama (PID $OLLAMA_PID)..."
kill $OLLAMA_PID 2>/dev/null || true
wait $OLLAMA_PID 2>/dev/null || true

exit $EXIT_CODE
