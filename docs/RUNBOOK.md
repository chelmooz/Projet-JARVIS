# RUNBOOK JARVIS Portable

## Démarrage

```bash
# Windows : double-clic sur launchers/JARVIS.bat
# Linux/Mac : ./launchers/JARVIS.sh

# Ou directement :
python jarvis.py            # Windows
python3 jarvis.py           # Linux/Mac
# → API : http://localhost:8000
# → Docs : http://localhost:8000/docs
```

Aucune installation requise. Le projet est 100% portable sur cle USB.

## Services

| Service | Port | Commande |
|---------|------|----------|
| JARVIS API | 8000 | `python jarvis.py` (Windows) / `python3 jarvis.py` (Linux/Mac) |
| Ollama | 11436 | `bin\win\ollama.exe serve` (Windows) / `bin/linux/ollama serve` (Linux/Mac) |

## Diagnostics

```bash
# Verifier les services
curl http://localhost:8000/api/status
# PowerShell : Invoke-RestMethod http://localhost:8000/api/status

# Verifier Ollama
curl http://localhost:11436/api/tags
# PowerShell : Invoke-RestMethod http://localhost:11436/api/tags

# Verifier les logs
cat logs/api.json            # Linux/Mac
type logs\api.json           # Windows
```

## Problemes courants

### Python portable introuvable
Le dossier `portable_python/` est manquant ou corrompu.
Re-telechargez le projet depuis la source d origine.

### Ollama ne demarre pas
```bash
# Verifier que le binaire Ollama est present
ls -la bin/linux/ollama                          # Linux/Mac
dir bin\win\ollama.exe                           # Windows
# Verifier les modeles disponibles
bin/linux/ollama list                            # Linux/Mac
bin\win\ollama.exe list                          # Windows
# Telecharger un modele du registre si necessaire (avec Ollama lance)
ollama pull hf.co/bartowski/Qwen2.5-7B-Instruct-GGUF:Q4_K_M
# Les modeles specifiques JARVIS sont importes depuis des .gguf locaux :
#   python scripts/import_gguf.py
```

### Port deja utilise
```bash
set PORT=8001 && python jarvis.py        # Windows (cmd)
$env:PORT=8001; python jarvis.py        # Windows (PowerShell)
PORT=8001 python3 jarvis.py             # Linux/Mac
```

## Tests & Lint

```bash
# Tests
python -m pytest -v                    # Windows
python3 -m pytest -v                   # Linux/Mac

# Linting
ruff check .

# Correction auto
ruff check --fix .
```

## Integration

```bash
# Docker (Ollama pour CI)
docker compose up -d
python -m pytest tests/test_integration_ollama.py -v    # Windows
python3 -m pytest tests/test_integration_ollama.py -v   # Linux/Mac

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
make clean       # supprime __pycache__, .pytest_cache, .ruff_cache
```

## Sauvegarde

```bash
# Linux/Mac
tar czf backup-$(date +%Y%m%d).tar.gz memory/ logs/ config/

# Windows (PowerShell)
Compress-Archive -Path memory, logs, config -DestinationPath backup-$(Get-Date -Format yyyyMMdd).zip
```
