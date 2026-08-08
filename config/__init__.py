"""Configuration JARVIS — package racine.

L'API typée historique (dataclasses ``AgentProfileConfig``/``ModelPreference``/
``CyberWorkflow``/``ComponentAsset``/``ComponentsConfig``, getters
``get_agent_profiles``/``get_model_preferences``/``get_cyber_workflows``/
``get_components``, ``reload``) a été supprimée : aucun appelant en production,
scripts ou tests (vérifié par grep exhaustif — voir docs/inventory-dead-code.md, MT-D4).

La configuration effective vit dans les sous-modules :
- ``config/constants.py``   : constantes runtime (ports, chemins, modèles)
- ``config/paths.py``       : chemins du système de fichiers
- ``config/agent_profiles.py`` : modèle configuré par agent (``model_for_agent``)
- ``config/*.json`` / ``config/*.yaml`` : données (profils, tailles, routage, outils)
"""
