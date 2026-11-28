"""Deterministic, fail-closed outcome verification for NEXUS autonomy."""

from dataclasses import dataclass, asdict
from typing import Callable, Any
import re


@dataclass
class VerificationResult:
    verified: bool = False
    verifier: str = ""
    verification_scope: str = "none"
    trusted_source: bool = False
    semantic_success_verified: bool = False
    learning_target: Any = None
    reason: str = "No registered verifier accepted this outcome."

    def to_dict(self):
        return asdict(self)


class OutcomeVerifierRegistry:
    def __init__(self):
        self._verifiers = {}

    def register(self, name: str, verifier: Callable):
        if not isinstance(name, str) or not re.fullmatch(
            r"[a-zA-Z0-9_.-]{1,80}", name
        ):
            raise ValueError("Invalid verifier name.")
        if not callable(verifier):
            raise TypeError("Verifier must be callable.")
        if name in self._verifiers:
            raise ValueError(f"Verifier already registered: {name}")
        self._verifiers[name] = verifier
        return name

    def names(self):
        return sorted(self._verifiers)

    def verify(self, name: str, *, task: str, execution: dict):
        verifier = self._verifiers.get(name)
        if verifier is None:
            return VerificationResult().to_dict()

        if not isinstance(task, str) or not task.strip():
            return VerificationResult(reason="Invalid task input.").to_dict()
        if not isinstance(execution, dict):
            return VerificationResult(reason="Invalid execution result.").to_dict()

        try:
            raw = verifier(task=task, execution=execution)
        except Exception:
            return VerificationResult(
                verifier=name,
                reason="Verifier raised an exception."
            ).to_dict()

        if not isinstance(raw, dict):
            return VerificationResult(
                verifier=name,
                reason="Verifier returned an invalid result."
            ).to_dict()

        # Require every trust assertion explicitly. No implicit approval.
        verified = raw.get("verified") is True
        trusted = raw.get("trusted_source") is True
        semantic = raw.get("semantic_success_verified") is True
        target = raw.get("learning_target")

        if not (verified and trusted and semantic and isinstance(target, dict)):
            return VerificationResult(
                verifier=name,
                reason="Verifier did not satisfy all learning-safety requirements."
            ).to_dict()

        # Store only the verifier's normalized target, never raw tool output.
        return VerificationResult(
            verified=True,
            verifier=name,
            verification_scope=str(raw.get("verification_scope", "semantic")),
            trusted_source=True,
            semantic_success_verified=True,
            learning_target=target,
            reason="Deterministic verifier accepted the outcome."
        ).to_dict()


    def verify_any(self, *, task: str, execution: dict):
        """Try registered verifiers; fail closed if none accepts the outcome."""
        for name in self.names():
            result = self.verify(name, task=task, execution=execution)
            if result.get("verified") is True:
                return result
        return VerificationResult(
            reason="No registered verifier verified this task."
        ).to_dict()


# No default verifier is registered. Task-specific verification must be
# explicitly implemented and registered by NEXUS integrations.
outcome_verifiers = OutcomeVerifierRegistry()


def verify_outcome(name: str, *, task: str, execution: dict):
    return outcome_verifiers.verify(name, task=task, execution=execution)
