"""Shared, safety-gated process supervision for external CPU miners."""

import json
import math
import os
import re
import subprocess
import time
from pathlib import Path
from contextlib import contextmanager

from .base import MinerAdapter
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config" / "mining"
STATE_DIR = CONFIG_DIR / "state"
LOG_DIR = ROOT / "logs" / "mining"


def read_json(path, default=None):
    try:
        with Path(path).open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError, TypeError):
        return default


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")
    os.replace(temporary, path)


def validate_config(data):
    if not isinstance(data, dict):
        raise ValueError("Miner configuration must be an object.")

    algorithm = data.get("algorithm")
    if not isinstance(algorithm, str) or not re.fullmatch(
        r"[A-Za-z0-9_.+-]{1,80}", algorithm
    ):
        raise ValueError("Invalid mining algorithm identifier.")

    pool = data.get("pool")
    if not isinstance(pool, str) or len(pool) > 512:
        raise ValueError("Invalid pool address.")

    try:
        parsed = urlsplit(pool)
        if parsed.scheme.lower() not in {
            "stratum+tcp", "stratum+ssl", "stratum+tls",
            "tcp", "ssl", "tls", "http", "https"
        }:
            raise ValueError()
        if not parsed.hostname or not parsed.port:
            raise ValueError()
    except ValueError:
        raise ValueError("Pool must be a valid supported URL with a port.")

    wallet = data.get("wallet")
    if not isinstance(wallet, str) or not wallet.strip() or len(wallet) > 512:
        raise ValueError("A valid wallet or pool username is required.")

    password = data.get("password", "x")
    if not isinstance(password, str) or len(password) > 256:
        raise ValueError("Invalid pool password.")

    coin = data.get("coin")
    if not isinstance(coin, str) or not re.fullmatch(
        r"[A-Za-z0-9_.-]{1,40}", coin
    ):
        raise ValueError("Invalid coin identifier.")

    threads = data.get("threads", 1)
    if isinstance(threads, bool) or not isinstance(threads, int):
        raise ValueError("Thread count must be an integer.")
    if not 1 <= threads <= (os.cpu_count() or 1):
        raise ValueError("Thread count exceeds available logical processors.")

    return {
        "coin": coin,
        "algorithm": algorithm,
        "pool": pool,
        "wallet": wallet.strip(),
        "password": password,
        "threads": threads,
    }


class ExternalMinerAdapter(MinerAdapter):
    """Common process manager. Subclasses supply documented CLI arguments."""

    engine = None
    executable_env = None
    executable_default = None

    def __init__(self):
        if not self.engine:
            raise ValueError("Miner engine identifier is missing.")
        self.config_path = CONFIG_DIR / f"{self.engine}.json"
        self.state_path = STATE_DIR / f"{self.engine}.json"
        self.log_path = LOG_DIR / f"{self.engine}.log"
        self.executable = Path(
            os.environ.get(
                self.executable_env,
                str(ROOT / self.executable_default)
            )
        ).expanduser().resolve()

    @property
    def capabilities(self):
        from .models import MinerCapabilities
        return MinerCapabilities(
            engine=self.engine,
            algorithms=(),
            coins=(),
            features=("configure", "status", "health", "start",
                      "stop", "recovery", "logs"),
            verified=False,
        )

    def configure(self, **kwargs):
        config = validate_config(kwargs)
        save_json(self.config_path, config)
        return {
            "status": "CONFIGURED",
            "engine": self.engine,
            "algorithm_verified": False,
            "note": "Configuration saved; executable and algorithm still require validation."
        }

    def load_config(self):
        data = read_json(self.config_path)
        if not isinstance(data, dict):
            raise RuntimeError(f"{self.engine} configuration is missing.")
        return validate_config(data)

    def build_command(self, config):
        raise NotImplementedError

    def _psutil(self):
        try:
            import psutil
            return psutil
        except ImportError:
            return None

    def _inspect_process(self, pid):
        """Distinguish exited processes from unverifiable process ownership."""
        psutil = self._psutil()
        if psutil is None:
            return "UNKNOWN", None

        try:
            process = psutil.Process(int(pid))
        except psutil.NoSuchProcess:
            return "EXITED", None
        except (psutil.Error, OSError, ValueError, TypeError):
            return "UNKNOWN", None

        try:
            actual = Path(process.exe()).resolve()
            expected = self.executable.resolve()

            if os.path.normcase(str(actual)) != os.path.normcase(str(expected)):
                return "UNKNOWN", None

            if not process.is_running():
                return "EXITED", None

            return "RUNNING", process

        except psutil.NoSuchProcess:
            return "EXITED", None
        except (psutil.Error, OSError, ValueError, TypeError):
            return "UNKNOWN", None

    def _owned_process(self, pid):
        """Compatibility helper; only returns a positively verified process."""
        status, process = self._inspect_process(pid)
        return process if status == "RUNNING" else None

    def status(self):
        if not self.state_path.exists():
            return {"status": "STOPPED", "engine": self.engine}

        state = read_json(self.state_path, None)
        if not isinstance(state, dict):
            return {
                "status": "UNKNOWN",
                "engine": self.engine,
                "reason": "Miner state file is unreadable or malformed."
            }

        pid = state.get("pid")
        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
            return {
                "status": "UNKNOWN",
                "engine": self.engine,
                "reason": "Miner state contains an invalid PID."
            }

        ownership, process = self._inspect_process(pid)

        if ownership == "EXITED":
            return {
                "status": "STOPPED",
                "engine": self.engine,
                "reason": "Process exit positively confirmed; recovery may be evaluated."
            }

        if ownership == "UNKNOWN":
            return {
                "status": "UNKNOWN",
                "engine": self.engine,
                "reason": "Process ownership or liveness could not be verified."
            }

        return {
            "status": "RUNNING",
            "engine": self.engine,
            "pid": process.pid,
            "executable": str(self.executable),
        }

    def health(self):
        from integrations.xmrig.hardware_monitor import collect
        return {
            "engine": self.engine,
            "process": self.status(),
            "hardware": collect(),
            "executable_exists": self.executable.is_file(),
        }

    def _validate_decision(self, decision, config):
        if not isinstance(decision, dict):
            raise RuntimeError("A profitability decision is required.")
        if decision.get("status") != "RECOMMENDATION_READY":
            raise RuntimeError("Profitability decision is not ready.")
        if decision.get("execution_authorized") is not True:
            raise RuntimeError("Central mining policy has not authorized execution.")

        selected = decision.get("selected")
        if not isinstance(selected, dict):
            raise RuntimeError("Selected mining opportunity is missing.")

        if selected.get("coin") != config["coin"]:
            raise RuntimeError("Selected coin does not match miner configuration.")
        if selected.get("algorithm") != config["algorithm"]:
            raise RuntimeError("Selected algorithm does not match miner configuration.")

        try:
            evaluated = float(decision["evaluated_at"])
            age = time.time() - evaluated
        except (KeyError, TypeError, ValueError, OverflowError):
            raise RuntimeError("Profitability decision timestamp is invalid.")

        if not math.isfinite(age) or age < -60 or age > 120:
            raise RuntimeError("Profitability decision is stale or from the future.")

        net = selected.get(
            "net_profit_per_day",
            selected.get("net_profit")
        )
        if isinstance(net, bool) or not isinstance(net, (int, float)):
            raise RuntimeError("Selected opportunity has no validated net profit.")
        if not math.isfinite(net) or net <= 0:
            raise RuntimeError("Selected opportunity is not net profitable.")

    def _safety_check(self):
        policy_path = ROOT / "config" / "xmrig.policy.json"
        emergency = ROOT / "config" / "MINING_EMERGENCY_STOP"
        policy = read_json(policy_path)

        if emergency.exists():
            raise RuntimeError("Emergency stop is active.")
        if not isinstance(policy, dict):
            raise RuntimeError("Mining policy is invalid.")
        for key in (
            "mining_enabled",
            "autonomous_execution_enabled",
            "stop_when_unprofitable",
        ):
            if policy.get(key) is not True:
                raise RuntimeError(f"Mining policy blocks execution: {key}")

        from integrations.xmrig.hardware_monitor import collect
        hardware = collect()

        if hardware.get("telemetry_complete") is not True:
            raise RuntimeError("Complete hardware telemetry is required.")

        limits = policy.get("profitability_limits", {})
        if not isinstance(limits, dict):
            raise RuntimeError("Profitability limits are invalid.")

        checks = (
            ("available_ram_gb", policy.get("minimum_available_ram_gb", 1.5), "min"),
            ("cpu_percent", limits.get("maximum_cpu_percent", 75), "max"),
            ("estimated_power_watts", limits.get("maximum_power_watts", 150), "max"),
            ("temperature_c", limits.get("maximum_temperature_c", 80), "max"),
        )
        for field, limit, direction in checks:
            value = hardware.get(field)
            if (isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)):
                raise RuntimeError(f"Hardware reading unavailable: {field}")
            if direction == "min" and value < limit:
                raise RuntimeError(f"Insufficient {field}: {value}; minimum {limit}.")
            if direction == "max" and value > limit:
                raise RuntimeError(f"Safety limit exceeded: {field}={value}.")

        return hardware

    @contextmanager
    def _process_lock(self):
        """Use the shared lock used by all mining engines."""
        from .process_lock import process_lock

        with process_lock(CONFIG_DIR / ".external-miners.lock"):
            yield

    def _ensure_no_other_external_miner(self):
        """Block unless both other mining engines are positively stopped."""
        from .process_lock import ensure_no_other_miner_running

        ensure_no_other_miner_running(self.engine)

    def start(self, profitability_decision=None):
        with self._process_lock():
            config = self.load_config()
            self._validate_decision(profitability_decision, config)

            current = self.status()
            if current.get("status") == "RUNNING":
                return {"status": "ALREADY_RUNNING", "engine": self.name}
            if current.get("status") != "STOPPED":
                raise RuntimeError(
                    "Mining blocked: existing process ownership is uncertain."
                )

            self._ensure_no_other_external_miner()

            if not self.executable.is_file():
                raise RuntimeError(f"Miner executable not found: {self.executable}")
            if self._psutil() is None:
                raise RuntimeError(
                    "Mining blocked: psutil is required for process ownership checks."
                )

            self._safety_check()
            command = self.build_command(config)
            process = subprocess.Popen(
                command,
                cwd=str(self.executable.parent),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=False,
            )

            try:
                time.sleep(0.25)
                if process.poll() is not None:
                    raise RuntimeError(
                        f"Miner exited during startup with code {process.returncode}."
                    )

                psutil = self._psutil()
                child = psutil.Process(process.pid)
                actual = Path(child.exe()).resolve()
                expected = self.executable.resolve()
                if actual != expected or not child.is_running():
                    raise RuntimeError(
                        "Miner startup verification failed: process identity "
                        "could not be confirmed."
                    )
            except Exception:
                try:
                    process.terminate()
                    process.wait(timeout=3)
                except Exception:
                    try:
                        process.kill()
                    except Exception:
                        pass
                raise

            self.save_state({
                "engine": self.name,
                "pid": process.pid,
                "executable": str(self.executable.resolve()),
                "started_at": time.time(),
            })
            return {
                "status": "STARTED",
                "engine": self.name,
                "pid": process.pid,
            }

    def stop(self):
        with self._process_lock():
            return self._stop_locked()

    def _stop_locked(self):
        state = read_json(self.state_path, {})
        pid = state.get("pid") if isinstance(state, dict) else None

        if not pid:
            return {"status": "NOT_RUNNING", "engine": self.engine}

        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
            return {
                "status": "STOP_BLOCKED",
                "reason": "Saved PID is invalid; state preserved.",
            }

        psutil = self._psutil()
        if psutil is None:
            return {
                "status": "STOP_BLOCKED",
                "reason": "psutil unavailable; state preserved.",
            }

        ownership, process = self._inspect_process(pid)

        if ownership == "EXITED":
            self.state_path.unlink(missing_ok=True)
            return {"status": "STOPPED", "engine": self.engine, "pid": pid}

        if ownership != "RUNNING" or process is None:
            return {
                "status": "STOP_BLOCKED",
                "reason": "Process ownership cannot be confirmed; state preserved.",
            }

        # Capture descendants only after verifying the parent executable.
        try:
            descendants = process.children(recursive=True)
        except psutil.NoSuchProcess:
            descendants = []
        except Exception as exc:
            return {
                "status": "STOP_BLOCKED",
                "reason": f"Could not inspect process tree: {exc}",
            }

        # Terminate descendants before their parent.
        targets = list(reversed(descendants)) + [process]

        try:
            for target in targets:
                try:
                    target.terminate()
                except psutil.NoSuchProcess:
                    pass

            _, alive = psutil.wait_procs(targets, timeout=10)

            if alive:
                for target in alive:
                    try:
                        target.kill()
                    except psutil.NoSuchProcess:
                        pass

                _, alive = psutil.wait_procs(alive, timeout=5)

            if alive:
                return {
                    "status": "STOP_FAILED",
                    "reason": "One or more verified process-tree members remain alive; state preserved.",
                }

        except Exception as exc:
            return {
                "status": "STOP_FAILED",
                "reason": str(exc),
            }

        # Confirm the original PID is no longer running before clearing state.
        final_state, _ = self._inspect_process(pid)
        if final_state != "EXITED":
            return {
                "status": "STOP_FAILED",
                "reason": "Parent process exit could not be confirmed; state preserved.",
            }

        self.state_path.unlink(missing_ok=True)
        return {"status": "STOPPED", "engine": self.engine, "pid": pid}

    def recover(self, profitability_decision=None):
        # Keep the shared lock held through validation and the restart.
        with self._process_lock():
            return self._recover_locked(profitability_decision)

    def _recover_locked(self, profitability_decision=None):
        """Restart only after verified exit and all recovery gates pass."""
        recovery_path = STATE_DIR / f"{self.engine}.recovery.json"

        with self._process_lock():
            current = self.status()
            if current.get("status") == "RUNNING":
                return {"status": "RUNNING", "engine": self.engine}
            if current.get("status") == "UNKNOWN":
                return {
                    "status": "RECOVERY_BLOCKED",
                    "reason": current.get("reason", "Process ownership is uncertain."),
                }

            state = read_json(self.state_path, None)
            if not isinstance(state, dict):
                return {
                    "status": "IDLE" if not self.state_path.exists() else "RECOVERY_BLOCKED",
                    "engine": self.engine,
                    "reason": "Previous process state is missing or invalid.",
                }

            pid = state.get("pid")
            if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
                return {
                    "status": "RECOVERY_BLOCKED",
                    "reason": "Saved process ID is invalid; state preserved.",
                }

            ownership, _ = self._inspect_process(pid)
            if ownership != "EXITED":
                return {
                    "status": "RECOVERY_BLOCKED",
                    "reason": "Previous process exit could not be positively confirmed; state preserved.",
                }

            if profitability_decision is None:
                return {
                    "status": "RESTART_BLOCKED",
                    "reason": "Fresh authorized profitability decision required.",
                }

            try:
                config = self.load_config()
                self._validate_decision(profitability_decision, config)

                policy = read_json(ROOT / "config" / "xmrig.policy.json", None)
                if not isinstance(policy, dict):
                    raise RuntimeError("Mining policy is missing or invalid.")
                if policy.get("autonomous_restart_enabled") is not True:
                    raise RuntimeError("Mining policy blocks autonomous restart.")

                limit = policy.get("maximum_restarts_per_hour")
                if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
                    raise RuntimeError("Hourly restart limit is missing or invalid.")

                # Recheck emergency stop, execution policy and hardware telemetry.
                self._safety_check()

                now = time.time()
                if recovery_path.exists():
                    history = read_json(recovery_path, None)
                    if not isinstance(history, dict) or not isinstance(history.get("attempts"), list):
                        raise RuntimeError("Recovery history is malformed; restart blocked.")
                    attempts = history["attempts"]
                else:
                    attempts = []

                if any(
                    isinstance(item, bool)
                    or not isinstance(item, (int, float))
                    or not math.isfinite(item)
                    or item > now + 60
                    for item in attempts
                ):
                    raise RuntimeError("Recovery history contains invalid timestamps.")

                recent = [float(item) for item in attempts if now - 3600 <= item <= now]
                if len(recent) >= limit:
                    raise RuntimeError(
                        f"Hourly restart limit reached ({len(recent)}/{limit})."
                    )

                # Persist before launch: failed attempts count toward the limit.
                recent.append(now)
                save_json(recovery_path, {"engine": self.engine, "attempts": recent})

            except Exception as exc:
                return {
                    "status": "RESTART_BLOCKED",
                    "engine": self.engine,
                    "reason": str(exc),
                }

        # start() obtains the shared lock again and rechecks ownership and policy.
        # The previous state file remains intact until start() verifies a replacement.
        return self.start(profitability_decision)

    def logs(self, lines=30):
        if isinstance(lines, bool) or not isinstance(lines, int) or not 1 <= lines <= 1000:
            raise ValueError("Log line count must be between 1 and 1000.")
        if not self.log_path.is_file():
            return []
        return self.log_path.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines()[-lines:]
