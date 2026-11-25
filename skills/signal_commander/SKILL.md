# Signal Commander

Signal Commander is NEXUS-AI's research intelligence and opportunity-discovery subsystem.

## Capabilities
- Recursive niche and sub-niche discovery.
- Multi-category trend and relationship discovery.
- Evidence-aware story verification and opportunity ranking.
- Persistent discovery memory and deduplication.
- Timestamped discovery reports.
- Agent research-task preparation and persistent task archival.
- Read-only intelligence dashboard and registry diagnostics.

## Intelligence tools
- `signal_commander_discover`: performs online discovery when explicitly invoked.
- `signal_commander_dashboard`: returns a read-only intelligence overview.
- `signal_commander_memory`: reads persistent discovery memory.
- `signal_commander_insights`: summarizes the latest discovery report and pipeline metrics.
- `signal_commander_report_search`: searches saved reports.
- `signal_commander_registry_audit`: audits the central tool registry.

## Safety
Dashboard, memory, report-search and registry-audit operations are read-only.
Discovery is a separate operation. Preparing or archiving an agent task does not execute it.
Signal Commander must not publish content, place trades, start mining, or perform other consequential external actions.
Publishing remains disabled by default.
