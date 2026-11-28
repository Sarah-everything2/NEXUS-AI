"""Universal adapter around the existing XMRig client."""

from integrations.xmrig import client as xmrig_client

from ..base import MinerAdapter
from ..models import MinerCapabilities


class XMRigAdapter(MinerAdapter):
    @property
    def name(self):
        return "xmrig"

    @property
    def capabilities(self):
        # Do not claim algorithm compatibility until profiles and
        # miner-specific support have been independently validated.
        return MinerCapabilities(
            engine="xmrig",
            algorithms=(),
            coins=(),
            features=(
                "status",
                "health",
                "start",
                "stop",
                "recovery",
                "logs",
                "pool_configuration",
            ),
            verified=False,
        )

    def status(self):
        return xmrig_client.status()

    def health(self):
        return xmrig_client.health()

    def start(self, profitability_decision=None):
        return xmrig_client.start(
            profitability_decision=profitability_decision
        )

    def stop(self):
        return xmrig_client.stop()

    def recover(self, profitability_decision=None):
        return xmrig_client.recovery_check(
            profitability_decision=profitability_decision
        )

    def logs(self, lines=30):
        return xmrig_client.logs(lines=lines)

    def configure(self, **kwargs):
        if "pools" in kwargs:
            return xmrig_client.configure_pools(
                coin=kwargs["coin"],
                algorithm=kwargs["algorithm"],
                pools=kwargs["pools"],
                threads=kwargs.get("threads", 25),
            )

        if "url" in kwargs:
            return xmrig_client.configure_pool(
                url=kwargs["url"],
                wallet=kwargs["wallet"],
                algorithm=kwargs["algorithm"],
                password=kwargs.get("password", "x"),
                tls=kwargs.get("tls", False),
            )

        raise ValueError(
            "Provide either pools or url-based XMRig configuration."
        )
