"""SRBMiner-MULTI CPU-only adapter."""

from ..external import ExternalMinerAdapter


class SRBMinerAdapter(ExternalMinerAdapter):
    engine = "srbminer-multi"
    executable_env = "NEXUS_SRBMINER_EXE"
    executable_default = "miners/srbminer/SRBMiner-MULTI.exe"

    @property
    def name(self):
        return self.engine

    def build_command(self, config):
        return [
            str(self.executable),
            "--algorithm-cpu", config["algorithm"],
            "--pool", config["pool"],
            "--wallet", config["wallet"],
            "--password", config["password"],
            "--cpu-threads", str(config["threads"]),
            "--disable-gpu",
        ]
