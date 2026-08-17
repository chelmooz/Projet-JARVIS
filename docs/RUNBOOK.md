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

## Déploiement KB (Reconstruction de l'index vectoriel)

L'index vectoriel (`memory/vector_index.json`) n'est **pas** commité dans git (taille > 100 Mo, limite GitHub 100 Mo/fichier). Il est reconstruit à la demande depuis les sources JSONL (`wiki/sources/*.jsonl`) qui, elles, sont versionnées.

### Reconstruction complète (nécessite Ollama running)

```bash
# 1. Verifier qu'Ollama tourne (port 11436)
curl http://localhost:11436/api/tags

# 2. Lancer la reconstruction (une seule commande)
python scripts/rebuild_index_run.py
```

Sortie attendue :
```
=== Reconstruction de l'index vectoriel KB ===
AVANT: total=XXX embedded=XXX pending=XXX
Sources manquantes détectées: [...]
Ingestion de <source>...
  <source>: N entrées, N chunks, N edges
...
Total ingéré: N entrées, N chunks, N edges
=== Vectorisation des documents en attente ===
AVANT vectorisation: total=XXX embedded=XXX pending=XXX
APRÈS vectorisation: total=XXX embedded=XXX pending=0
Vectorisés: N documents
Smoke test 'Kerberoasting T1558.003' (top_k=1): results=1
  id=... agent=... score=...
=== Index KB reconstruit avec succès ===
```

### Comportement

- **Détection intelligente** : compare les sources JSONL (`wiki/sources/*.jsonl`) à l'index existant via `metadata.source`. Seules les sources manquantes sont ingérées (pas de ré-ingestion, pas de doublons grâce à la déduplication O(1) par hash SHA-256 du texte).
- **Vectorisation** : `vectorize_pending()` calcule les embeddings par lots de 32 (batch `embed_batch` MT-KB-L2i). Si `pending=0`, rien à faire.
- **Fail-open Ollama** : si Ollama n'est pas joignable (port 11436), le script affiche un message clair et sort sans modifier l'index.
- **Idempotent** : relancer le script ne ré-ingère pas les sources déjà présentes.

### Sur clef USB (déploiement terrain)

L'index vectoriel (`memory/vector_index.json`) **est déjà présent** sur la clef USB prête à l'emploi. **Aucune reconstruction nécessaire** — il suffit de lancer `launchers/JARVIS.bat` (Windows) ou `./launchers/JARVIS.sh` (Linux/Mac). Ollama doit être disponible (fourni dans `bin/win/ollama.exe` ou `bin/linux/ollama`).

La reconstruction n'est nécessaire que si :
- L'index a été corrompu/supprimé
- De nouvelles sources JSONL ont été ajoutées dans `wiki/sources/`
- On veut forcer une ré-vectorisation complète (supprimer `memory/vector_index.json` avant relance)
