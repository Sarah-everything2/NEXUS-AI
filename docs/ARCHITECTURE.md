# Architecture Overview

NEXUS AI is organized into modular layers:

- `core/`: application orchestration, agent routing and CLI.
- `agents/`: specialist agent implementations.
- `skills/`: reusable task capabilities.
- `tools/`: callable tools exposed to agents.
- `integrations/`: external services and local bridge clients.
- `config/`: application configuration.
- `data/`, `memory/`, `logs/`: local runtime data and records.
- `tests/`: automated verification.
- `docs/`: project, security and release documentation.

External actions must be permission-gated. Publishing, financial actions, destructive file operations and other consequential actions must retain their approval and safety controls.

The MT5 integration reuses the existing local bridge. It must remain restricted to the existing Headway-Demo account; real-money trading is not authorized.
