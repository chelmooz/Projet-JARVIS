# Modèles installés — JARVIS Portable

Table ci‑dessous : état des modèles stockés dans J:\Projet JARVIS\models\ollama (sources hf.co lorsque disponible).

| Modèle (Ollama) | Source | Statut | Remarques |
|---|---|---|---|
| `hf.co/Qwen/Qwen2.5-7B-Instruct-GGUF` | hf.co | Présent | manifest et blobs présents (7b)
| `hf.co/nomic-ai/nomic-embed-text-v2-moe-GGUF:Q4_K_M` | hf.co | Présent | embedding
| `hf.co/Melvin56/Phi-4-mini-instruct-abliterated-GGUF:Q4_K_M` | hf.co | Présent | petit modèle instruct
| `hf.co/deepreinforce-ai/Ornith-1.0-9B-GGUF` | hf.co | Présent | 9B
| `hf.co/bartowski/DeepSeek-Coder-V2-Lite-Instruct-GGUF:Q4_K_M` | hf.co | En attente | pull recommandé
| `hf.co/leafspark/Llama-3.2-11B-Vision-Instruct-GGUF:Q4_K_M` | hf.co | En attente | pull recommandé
| `igorls/gemma-4-E4B-it-heretic-GGUF:Q4_K_M` | registry.ollama.ai | Présent | manifest importé depuis registry.ollama.ai

## Notes
- Les pulls hf.co ont été ciblés vers le répertoire portable J:\Projet JARVIS\models\ollama ; les manifests trouvés sous manifests\registry.ollama.ai\library indiquent plusieurs modèles déjà présents.
- Les fichiers *-partial* ont été supprimés pour éviter des pulls corrompus. Si un pull échoue, relancer avec --verbose et consulter les logs dans la racine J:\ (pull-*.log).

---

Mettre à jour ce document après vérification runtime : démarrer Jarvis/Ollama portable avec `$env:OLLAMA_MODELS='J:\Projet JARVIS\models\ollama'`, puis exécuter `curl http://127.0.0.1:11436/api/agents` pour lister les agents exposés.
