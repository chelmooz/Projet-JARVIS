# Binaires multiplateforme — Ollama

## Structure

```
bin/
├── linux/          → Ollama pour Linux (x86_64)
├── mac/            → Ollama pour macOS (Universal: x86_64 + Apple Silicon)
├── win/            → Ollama pour Windows (x86_64)
├── diagnostic/     → Outils de diagnostic Windows (Sysinternals + smartctl)
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

### Windows (`diagnostic/`)
- **handle64.exe** — Lister les handles et fichiers ouverts (Sysinternals)
- **PsInfo64.exe** — Informations système détaillées (Sysinternals)
- **psloglist64.exe** — Lire les journaux d'événements Windows (Sysinternals)
- **psping64.exe** — Test de connectivité réseau avancé (Sysinternals)
- **PsService64.exe** — Gestion des services Windows (Sysinternals)
- **smartctl.exe** — Santé des disques S.M.A.R.T.

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

## Points d'attention avant distribution

- [x] Mettre à jour `linux/ollama` vers la version stable 0.134.0
- [ ] Signer le binaire macOS avec un certificat Apple Developer (éviter le blocage Gatekeeper)
- [ ] Considérer Git LFS pour versionner ces binaires (taille totale ~143 MB)
