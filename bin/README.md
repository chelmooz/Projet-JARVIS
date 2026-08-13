# Binaires multiplateforme — Ollama

## Structure

```
bin/
├── linux/          → Ollama pour Linux (x86_64)
├── mac/            → Ollama pour macOS (Universal: x86_64 + Apple Silicon)
├── win/            → Ollama pour Windows (x86_64)
├── diagnostic/     → Outils de diagnostic (sous-dossier par OS)
│   ├── win/        →   Windows (Sysinternals + smartctl + witr.exe)
│   ├── linux/      →   Linux (witr)
│   └── darwin/     →   macOS (witr arm64 + witr-amd64)
├── VERSION.json    → Manifeste des versions embarquées
└── README.md       → Ce fichier
```

## Versions embarquées

| Plateforme | Version      | Architecture         | Statut    |
|------------|--------------|----------------------|-----------|
| Linux      | 0.134.0      | x86_64               | ✅ Stable |
| macOS      | 0.134.0      | Universal (x64+arm64)| ✅ Stable |
| Windows    | 0.134.0      | x86_64               | ✅ Stable |

## Outils de diagnostic

> Structure par OS : `diagnostic/{win,linux,darwin}/` — les binaires witr Linux (ELF) et macOS (Mach-O) portent le même nom et ne peuvent pas coexister dans un dossier flat.
>
> **SHA256 par plateforme** : `config/diagnostic_tools.yaml` déclare `sha256` (win32), `linux_sha256` (linux) et `darwin_sha256` (darwin), résolus par `resolve_expected_sha256()` selon `sys.platform` (repli sur `sha256` si la clé spécifique est absente). Hash vide = vérification ignorée.

### Windows (`diagnostic/win/`)
- **handle64.exe** — Lister les handles et fichiers ouverts (Sysinternals)
- **PsInfo64.exe** — Informations système détaillées (Sysinternals)
- **psloglist64.exe** — Lire les journaux d'événements Windows (Sysinternals)
- **psping64.exe** — Test de connectivité réseau avancé (Sysinternals)
- **PsService64.exe** — Gestion des services Windows (Sysinternals)
- **smartctl.exe** — Santé des disques S.M.A.R.T.
- **witr.exe** — Explique pourquoi un processus/port/service tourne (ancestry chain, JSON natif)

### Linux (`diagnostic/linux/`) — witr
```bash
chmod +x bin/diagnostic/linux/witr
./bin/diagnostic/linux/witr --version
./bin/diagnostic/linux/witr --json <process|port|service>
```

### macOS (`diagnostic/darwin/`) — witr
```bash
chmod +x bin/diagnostic/darwin/witr   # Apple Silicon (arm64)
chmod +x bin/diagnostic/darwin/witr-amd64  # Intel (amd64)
./bin/diagnostic/darwin/witr --version
```

> **Note Gatekeeper macOS** : si le binaire est bloqué :
> `xattr -dr com.apple.quarantine bin/diagnostic/darwin/witr`

### witr — limitations par OS (v0.3.3)
- Capability warnings, Snap/Flatpak/tmux/screen detection, schedule detection : **Linux-only**
- `--json` disponible sur les 3 OS, mais certaines features renvoient des données partielles hors Linux — à refléter dans le prompt des agents.

### Linux
```bash
# Diagnostic disques SMART (smartmontools systeme)
sudo smartctl -a /dev/sda 2>/dev/null || echo "smartmontools non installe (optionnel)"

# Informations systeme
uname -a && lscpu && free -h && df -h

# Ports et processus
ss -tulnp
```

### macOS
```bash
# Diagnostic disques SMART (smartmontools Homebrew)
brew list smartmontools 2>/dev/null && sudo smartctl -a /dev/disk0 || echo "smartmontools non installe (optionnel)"

# Informations systeme
system_profiler SPHardwareDataType
```

## Utilisation

### Linux
```bash
chmod +x bin/linux/ollama
./bin/linux/ollama serve
```

### macOS
```bash
chmod +x bin/mac/ollama
./bin/mac/ollama serve
```

> **Note macOS** : Si Gatekeeper bloque le binaire, executer :
> `xattr -dr com.apple.quarantine bin/mac/ollama`
> ou passer par Préférences Système → Confidentialité & Sécurité.

### Windows
```cmd
bin\win\ollama.exe serve
```

