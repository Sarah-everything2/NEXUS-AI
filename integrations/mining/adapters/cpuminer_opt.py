"""cpuminer-opt CPU-only adapter."""

from ..external import ExternalMinerAdapter


class CpuMinerOptAdapter(ExternalMinerAdapter):
    engine = "cpuminer-opt"
    executable_env = "NEXUS_CPUMINER_OPT_EXE"
    executable_default = "miners/cpuminer-opt/cpuminer.exe"

    @property
    def name(self):
        return self.engine

    def build_command(self, config):
        return [
            str(self.executable),
            "-a", config["algorithm"],
            "-o", config["pool"],
            "-u", config["wallet"],
            "-p", config["password"],
            "-t", str(config["threads"]),
        ]
