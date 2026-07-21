# Architecture — JARVIS Portable Edition

Schéma des couches (architecture hexagonale / ports & adapters) :

```mermaid
graph TD
    %% Styling
    classDef client fill:#3b82f6,stroke:#1d4ed8,stroke-width:2px,color:#fff;
    classDef api fill:#10b981,stroke:#047857,stroke-width:2px,color:#fff;
    classDef core fill:#8b5cf6,stroke:#6d28d9,stroke-width:2px,color:#fff;
    classDef infra fill:#64748b,stroke:#334155,stroke-width:2px,color:#fff;

    UI["Interface Web<br><code>static/</code> (HTML/CSS/JS)<br><code>localhost:8000</code>"]:::client
    CTRL["controllers / routes<br><code>agents, jarvis, conversations, documents, analytics, files, skills</code><br>+ <code>context.py</code> (CSP, ratelimit)"]:::api
    PORTS["ports /<br>Protocols abstraits (<code>InferencePort</code>, <code>FilePort</code>...)"]:::core
    
    subgraph Core Logic ["Logique Métier & Orchestration"]
        AGENTS["agents/<br>Factory + profils (5 agents)"]:::core
        SERVICES["services/<br>Inference, vector, memory, launcher, sanitize, skills"]:::core
        GRAPH["graph/<br>Orchestration <code>AgentGraph</code> séquentiel"]:::core
    end

    ADAPT["adapters/<br><code>ollama_adapter.py</code>"]:::infra
    OLLAMA[("Ollama portable (11436)<br>+ Modèles GGUF locaux")]:::infra

    %% Connections
    UI -->|HTTP / FastAPI| CTRL
    CTRL --> PORTS
    PORTS --> AGENTS
    PORTS --> SERVICES
    PORTS --> GRAPH
    SERVICES --> ADAPT
    ADAPT --> OLLAMA
```

Stockage local (JSON) : `memory/` (conversations, habits, analytics, vector_index)
Démarrage             : `jarvis.py` → `ProcessManager` (Ollama + JARVIS Core)

## Flux d'une requête

1. L'UI envoie `POST /api/jarvis` (ou `/api/agents`, `/api/vision`...).
2. Le routeur FastAPI appelle `graph/AgentGraph` (orchestrateur séquentiel).
3. L'agent résout le modèle via `selector.py` puis `services/inference.py`.
4. L'adaptateur Ollama génère la réponse (Embeddings via `vector_embedder`).
5. Résultat renvoyé à l'UI ; la conversation est persistée par `conversation.py`.

## Décisions d'architecture (ADR)

Voir `docs/adr/` (ADR-001 à ADR-007) : MVC/ports, suppression technos, sandbox
CPU-only, fallback embeddings histogramme, sécu offline single-backend.
