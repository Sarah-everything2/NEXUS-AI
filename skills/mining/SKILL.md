# NEXUS AI Mining Operations

## XMRig Integration

NEXUS can manage the existing Windows XMRig installation.

Available tools:
- xmrig_status: inspect miner process status.
- xmrig_health: inspect system memory and miner status.
- xmrig_logs: inspect recent miner output.
- xmrig_configure_pool: configure an explicitly supplied pool and wallet.
- xmrig_start: start mining after approval.
- xmrig_stop: stop the miner launched by NEXUS.

## Safety
- Never start mining without explicit approval.
- Never use the XMRig donation endpoint as the user's pool.
- Never request wallet seed phrases or private keys.
- Preserve the original XMRig configuration.
- Use the NEXUS runtime configuration for mining.
- Never change pool, wallet, or CPU settings without approval.
- Clearly distinguish estimated rewards from actual pool payouts.
- Monitor available RAM and CPU usage.
- Do not promise profitability.
