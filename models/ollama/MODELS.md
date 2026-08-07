# Modèles installés — JARVIS Portable

Table ci‑dessous : état des modèles stockés dans J:\Projet JARVIS\models\ollama (sources hf.co lorsque disponible).

| Modèle (Ollama) | Source | Statut | Remarques |
|---|---|---|---|---|
| `hf.co/bartowski/Qwen2.5-7B-Instruct-GGUF:Q4_K_M` | hf.co | À pull | Modèle par défaut, polyvalent
| `hf.co/bartowski/ibm-granite_granite-4.1-8b-GGUF:Q4_K_M` | hf.co | À pull | Code & refactoring — @dev
| `hf.co/GGUF-A-Lot/DeepHat-V1-7B-GGUF:Q4_K_M` | hf.co | À pull | Sécurité offensive & défensive — @cyber
| `hf.co/fdtn-ai/Foundation-Sec-8B-Reasoning-Q8_0-GGUF:Q8_0` | hf.co | À pull | Analyse réseau & SOC — @network
| `hf.co/Melvin56/Phi-4-mini-instruct-abliterated-GGUF:Q4_K_M` | hf.co | À pull | Petit modèle CPU, sans filtre
| `hf.co/leafspark/Llama-3.2-11B-Vision-Instruct-GGUF:Q4_K_M` | hf.co | À pull | Vision multimodale — @vision
| `hf.co/nomic-ai/nomic-embed-text-v2-moe-GGUF:Q4_K_M` | hf.co | À pull | Embeddings RAG (768d)

## Notes
- Les pulls hf.co ont été ciblés vers le répertoire portable J:\Projet JARVIS\models\ollama ; les manifests trouvés sous manifests\registry.ollama.ai\library indiquent plusieurs modèles déjà présents.
- Les fichiers *-partial* ont été supprimés pour éviter des pulls corrompus. Si un pull échoue, relancer avec --verbose et consulter les logs dans la racine J:\ (pull-*.log).

---

Mettre à jour ce document après vérification runtime : démarrer Jarvis/Ollama portable avec `$env:OLLAMA_MODELS='J:\Projet JARVIS\models\ollama'`, puis exécuter `curl http://127.0.0.1:11436/api/agents` pour lister les agents exposés.
