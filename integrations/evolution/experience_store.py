import json
from pathlib import Path
from datetime import datetime, timezone
from .governance import redact

class ExperienceStore:
    def __init__(self, root="data/intelligence/evolution"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.experiences = self.root / "experiences.jsonl"
        self.dataset = self.root / "curated_dataset.jsonl"

    def capture(self, task, outcome, approved=False, provenance=None):
        if not isinstance(approved, bool):
            raise TypeError("approved must be a boolean.")
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "task": redact(task),
            "outcome": redact(outcome),
            "provenance": redact(provenance or {}),
            "approved": approved,
            "curated": False,
        }
        with self.experiences.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return {"saved": True, "curated": False}

    def find_latest(self, cycle_id):
        """Retrieve the persisted experience for one autonomy cycle."""
        if not isinstance(cycle_id, str) or not cycle_id:
            return None
        if not self.experiences.exists():
            return None

        with self.experiences.open("r", encoding="utf-8") as f:
            for line in reversed(f.readlines()):
                try:
                    record = json.loads(line)
                except (ValueError, TypeError):
                    continue
                provenance = record.get("provenance", {})
                if isinstance(provenance, dict) and provenance.get("cycle_id") == cycle_id:
                    return record
        return None

    def curate(self, record, approved=False, autonomous=False):
        if approved is not True and autonomous is not True:
            raise PermissionError("Experience curation is not authorized.")

        safe = redact(record)
        if not isinstance(safe, dict):
            raise ValueError("Experience record must be an object.")

        provenance = safe.get("provenance", {})
        if not isinstance(provenance, dict):
            raise ValueError("Experience provenance is invalid.")

        if approved is True:
            if safe.get("approved") is not True:
                raise ValueError("Human approval is not recorded.")
            safe["curation_method"] = "human_approved"

        elif autonomous is True:
            # Machine verification is deliberately distinct from human approval.
            if safe.get("approved") is True:
                raise ValueError("Autonomous curation cannot alter approval provenance.")
            if provenance.get("semantic_success_verified") is not True:
                raise PermissionError("Semantic task success has not been verified.")
            if provenance.get("trusted_source") is not True:
                raise PermissionError("Experience source has not passed trust checks.")
            if provenance.get("tool_execution_success") is not True:
                raise PermissionError("Tool execution was not verified successful.")
            safe["curation_method"] = "autonomous_verified"

        safe["curated"] = True
        safe["curated_at"] = datetime.now(timezone.utc).isoformat()

        with self.dataset.open("a", encoding="utf-8") as f:
            f.write(json.dumps(safe, ensure_ascii=False) + "\n")

        return {
            "curated": True,
            "curation_method": safe["curation_method"],
            "human_approved": safe.get("approved") is True
        }
