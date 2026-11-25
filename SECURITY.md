# Security Policy

## Reporting a Vulnerability
Please report security vulnerabilities privately to the repository maintainer. Do not publish credentials, access tokens, private account information, or exploit details in public issues.

## Security Principles
- Keep API keys, OAuth secrets, access tokens, passwords and broker credentials out of source control.
- Use environment variables or appropriately protected local configuration for credentials.
- Never commit `.env` files, personal settings, token stores, memory databases or local backups.
- Review permissions before enabling external integrations.
- Keep autonomous actions subject to configured authorization, risk controls and emergency-stop mechanisms.

## Financial and External Actions
Trading, mining, publishing and other consequential integrations require appropriate account configuration and authorization. Demo trading is not evidence of live-trading safety. Never assume a feature is safe for production without reviewing its implementation and configuration.

## Scope
This project is provided as open-source software. No security guarantee or financial outcome is promised. Users should independently review integrations and third-party services before enabling them.
