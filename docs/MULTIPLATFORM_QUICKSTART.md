# NEXUS-AI Multi-platform Quickstart

## Windows PowerShell

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip check
python -m core.cli
```

If activation is restricted, use:
` .\.venv\Scripts\python.exe -m core.cli `

## Linux and macOS

```bash
chmod +x scripts/install-unix.sh scripts/run.sh
./scripts/install-unix.sh
./scripts/run.sh
```

## Android Termux

```bash
chmod +x scripts/install-termux.sh scripts/run.sh
./scripts/install-termux.sh
./scripts/run.sh
```

Some optional integrations and native dependencies may not work on every Android device.

## iPhone and iPad PWA

Open the dashboard in Safari and choose Share, then Add to Home Screen.
PWA installation and service workers require HTTPS, except localhost for
development on that same device. Remote HTTP does not qualify.

## HTTPS and network exposure

Keep the dashboard localhost-only by default. Do not bind to `0.0.0.0`,
expose it to a LAN, or publish it publicly without authentication, TLS,
authorization, and a security review.

## Offline limitations

Only `/`, the manifest, and the icon are cached. `/api/` responses, chat,
account data, and live system state are never cached. Offline mode cannot
provide AI responses.

## Security and authorization

Keep `.env`, credentials, tokens, private configuration, and local databases
out of source control. Preserve approval gates. Installation does not start
NEXUS or enable autonomous mode. Trading, publishing, uploads, and external
service activation require explicit authorization.
