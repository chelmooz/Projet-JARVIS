# RUNBOOK JARVIS Portable

## Démarrage

```bash
# Windows : double-clic sur launchers/JARVIS.bat
# Linux/Mac : ./launchers/JARVIS.sh

# Ou directement :
python3 jarvis.py
# → API : http://localhost:8000
# → Docs : http://localhost:8000/docs
```

Aucune installation requise. Le projet est 100% portable sur cle USB.

## Services

| Service | Port | Commande |
|---|---|---|
| JARVIS API | 8000 | `python3 jarvis.py` |
| Ollama | 11436 | `bin/linux/ollama serve` (ou ./launchers/JARVIS.sh) |

## Diagnostics

```bash
# Verifier les services
curl http://localhost:8000/api/status

# Verifier Ollama
curl http://localhost:11436/api/tags

# Verifier les logs
cat logs/api.json
```

## Problemes courants

### Python portable introuvable
Le dossier `portable_python/` est manquant ou corrompu.
Re-telechargez le projet depuis la source d origine.

### Ollama ne demarre pas
```bash
# Verifier que le binaire Ollama est present
ls -la bin/linux/ollama
# Verifier les modeles disponibles
bin/linux/ollama list
# Telecharger un modele du registre si necessaire (avec Ollama lance)
ollama pull qwen2.5
# Les modeles specifiques JARVIS sont importes depuis des .gguf locaux :
#   python scripts/import_gguf.py
```

### Port deja utilise
```bash
PORT=8001 python3 jarvis.py
```

## Tests & Lint

```bash
# Tests
python3 -m pytest -v

# Linting
ruff check .

# Correction auto
ruff check --fix .
```

## Integration

```bash
# Docker (Ollama pour CI)
docker compose up -d
python3 -m pytest tests/test_integration_ollama.py -v

# Portable (Linux)
./scripts/run_integration_tests.sh

# Portable (Windows)
scripts\run_integration_tests.bat
```

## CI

```bash
# La CI GitHub Actions s'execute sur chaque push/PR vers main.
# Configuration : .github/workflows/ci.yml
# Services : Ollama via Docker (port 11436)
# Etapes : ruff check -> unit tests -> integration tests
```

## Diagnostic rapide

```bash
python3 jarvis.py --diag
```

Affiche un tableau colore (OK / WARN / FAIL) avec l'etat de chaque
composant : OS, CPU, RAM, GPU, Python, binaires, ports, internet,
espace disque. Exit code 0 si tout OK, 1 si au moins un FAIL critique.

Un endpoint API est aussi disponible :

```bash
curl http://localhost:8000/api/diag
```

## Makefile

```bash
make test        # pytest
make lint        # ruff check
make lint-fix    # ruff check --fix
make run         # python3 jarvis.py
make clean       # supprime __pycache__, .pytest_cache
```

## Sauvegarde

```bash
# Donnees utilisateur
tar czf backup-$(date +%Y%m%d).tar.gz memory/ logs/ config/
```
