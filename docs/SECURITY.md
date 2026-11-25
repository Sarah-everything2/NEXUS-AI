# Security and Permissions

- Keep API keys, OAuth tokens, passwords, private account details and `.env` files out of version control.
- Use least-privilege permissions for connected services and local files.
- Require human approval for external publishing and consequential actions.
- Never expose credentials in logs, terminal output or exception messages.
- MT5 is restricted to the existing Headway-Demo account; live-account trading is not authorized.
- Preserve demo identity verification, trade approvals, risk limits, stop-loss, take-profit, stale-quote checks, audit logging and emergency-stop controls.
- Static tests must not submit orders, publish content, launch miners or upload media.
- Rotate credentials if exposure is suspected.
