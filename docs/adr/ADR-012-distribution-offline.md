# ADR-012 — Distribution offline : lockfile + vendoring des wheels

- **Statut** : Accepté
- **Date** : 14/08/2026

## Contexte

La distribution JARVIS Portable est censée s'installer sur des machines
isolées (clés USB, postes audités sans réseau). Historiquement, les
dépendances Python étaient installées depuis `pyproject.toml` par
`scripts/install.py`, avec résolution pip en ligne au moment de l'install :
impossible de garantir la reproductibilité, ni l'installation hors ligne.

Par ailleurs, le projet avait déjà un `requirements.txt` (mentionné au
CHANGELOG) qui dérivait — aucun outil ne l'épingleait depuis le code source.

## Décision

### 1. Sources uniques de vérité

- `pyproject.toml` : déclaration volontaire des dépendances (plages), rien
  d'autre.
- `uv.lock` (racine) : épinglage **complet et reproductible**, généré par
  `uv lock`, versionné dans git. Toute modification de dépendance passe par
  `uv add` / `uv lock`.
- `requirements.lock` (racine) : export plat de `uv.lock` au format
  requirements.txt (`uv export --format requirements-txt --no-hashes
  --no-emit-project`), consommable par pip pour le vendoring. Versionné lui
  aussi : c'est lui la cible de `vendor_wheels.py`.

### 2. Vendoring des wheels (installation offline)

`scripts/vendor_wheels.py` télécharge les distributions binaires pour 3
plateformes (win_amd64, manylinux_2_17_x86_64, macosx_11_0_arm64, Python
3.12, binaires uniquement) dans `vendor_wheels/` — dossier **ignoré par git**
(~500 Mo cumulés, produit au moment de préparer la clé de déploiement, pas
dans le dépôt).

Le procédé doit composer avec une contrainte pip (26+) : dès qu'on croise
`--platform` / `--python-version`, pip exige `--only-binary=:all:` (ou
`--no-deps`). Comme `requirements.lock` est plat et complet, le résolveur de
dépendances n'est pas nécessaire au téléchargement :

1. wheels : `pip download -r requirements.lock --no-deps
   --only-binary=:all: --platform … --python-version 3.12`
2. exception sdist : `antlr4-python3-runtime==4.9.3` n'a aucune wheel (il est
   épinglé `==4.9.*` par omegaconf, dépendance de rapidocr) → téléchargé une
   seule fois en sdist (pur Python, compilé à l'install par setuptools,
   présent dans le Python portable).

Rationale : `uv pip download` (prévu au ROADMAP) a été retiré de uv 0.12.3 ;
`pip download` offre des arguments identiques et est disponible partout où
pip est installé, ce qui évite de dépendre d'uv sur la clé de déploiement.

### 3. Installation offline

`scripts/install.py` détecte `vendor_wheels/` et, s'il est présent pour la
plateforme courante, installe en `--no-index --find-links vendor_wheels[/plat]`
(voir `_vendor_find_links`). Sans dossier de vendoring, il conserve le
comportement en ligne (avec mise à jour pip/setuptools/wheel au préalable).

## Conséquences

- Reproductibilité : les versions sont épinglées une fois pour toutes dans
  `uv.lock` et `requirements.lock`, le vendoring et l'install consomment la
  même source.
- Offline : une clé préparée avec `vendor_wheels/` s'installe sans réseau.
- Léger pour le dépôt : les wheels ne sont pas versionnées (500 Mo), seul
  l'outil de génération l'est.
- Poids opérateur : avant de graver une clé hors ligne, il faut exécuter
  `python scripts/vendor_wheels.py` (ou bannir le mode offline).
