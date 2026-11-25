# Release Checklist

## Code quality
- [ ] Python compilation passes.
- [ ] All automated tests pass.
- [ ] Git diff whitespace check passes.
- [ ] No accidental duplicate or obsolete implementations.
- [ ] Backups and untracked files reviewed before release.

## Security and credentials
- [ ] No API keys, OAuth tokens, passwords or private keys committed.
- [ ] Local settings and secrets excluded from Git.
- [ ] Credential-like files and tracked content audited.
- [ ] File permissions reviewed for secrets and configuration.
- [ ] Logs do not disclose credentials or private account information.
- [ ] External integrations use least-privilege permissions.

## MT5 safety
- [ ] Existing Headway-Demo account identity is verified.
- [ ] Demo-only restriction remains enabled.
- [ ] Live-account execution remains disabled.
- [ ] Trade confirmation and one-time approval remain enforced.
- [ ] Volume, risk and position limits remain enforced.
- [ ] Stop-loss and take-profit remain mandatory.
- [ ] Stale-quote checks and emergency stop are verified.
- [ ] No real order is submitted during release testing.

## Integrations
- [ ] OpenMausBot integration reviewed.
- [ ] X publishing approval tested without publishing.
- [ ] TikTok integration reviewed without publishing.
- [ ] Mining reviewed without launching workloads.
- [ ] Video clipping reviewed without uploading media.
- [ ] YouTube automation reviewed without uploading media.

## Documentation and release
- [ ] Installation instructions verified on a clean environment.
- [ ] Architecture and configuration documented.
- [ ] Troubleshooting guidance completed.
- [ ] License and third-party notices reviewed.
- [ ] Demo and presentation prepared.
- [ ] Final Git changes reviewed.
- [ ] Release explicitly approved.
