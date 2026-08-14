# ADR-011 — Sandbox fichiers : fail-closed (aucun accès sans configuration)

- **Statut** : Accepté
- **Date** : 14/08/2026

## Contexte

L'UI locale propose un explorateur de dossiers (« File browser ») pour autoriser
les chemins que le LLM peut lire. Historiquement, la doc
(`.env.example:37`) affirmait :

> « Si vide, l'utilisateur peut autoriser n'importe quel dossier »

Ce commentaire est une relique d'un design antérieur (fail-open) qui
contredisait le comportement réel du code.

## Comportement réel (constat)

`services/file_system.py` (`_is_inside_sandbox`, lignes 112-114) est
**fail-closed** :

```python
sandbox = os.environ.get("JARVIS_FILES_SANDBOX_ROOT")
if not sandbox:
    raise FileSystemError("Sandbox non configuré : définissez JARVIS_FILES_SANDBOX_ROOT")
```

Sans `JARVIS_FILES_SANDBOX_ROOT` défini, **toute** opération sur les fichiers
lève une erreur explicite : il est impossible d'autoriser un dossier. Il n'y a
aucun chemin de « tout autoriser », ni par défaut ni via l'UI.

## Décision

Le fail-closed est le comportement **retenu et garanti** :

- Le sandbox n'est activé que si `JARVIS_FILES_SANDBOX_ROOT` est défini.
- Absence de configuration ⇒ refus formel (`FileSystemError`), pas de
  dégradation silencieuse vers un accès large.
- Le commentaire `.env.example` est corrigé pour refléter ce contrat, et
  pointe vers cet ADR.

## Conséquences

- Sécurité : par défaut, aucun chemin n'est lisible par le LLM — exposition
  minimale sur une machine sans configuration.
- Configuration : l'utilisateur qui veut le file browser doit définir
  explicitement `JARVIS_FILES_SANDBOX_ROOT`.
- Cohérence : le code, les tests (`tests/test_file_system.py`, fixture
  `sandbox_root` qui pose la variable sur `tmp_path`) et la doc parlent
  désormais le même langage.
