import json
from pathlib import Path
from datetime import datetime, timezone

class ModelRegistry:
    def __init__(self, root="data/intelligence/model_registry"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "registry.json"
        if not self.path.exists():
            self._save({
                "active_model": None,
                "candidates": {},
                "history": [],
                "automatic_promotion": False,
                "manual_promotion_enabled": False,
            })

    def _load(self):
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, data):
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        temp.replace(self.path)

    def register_candidate(self, candidate_id, metadata):
        if (
            not isinstance(candidate_id, str)
            or not candidate_id.strip()
            or len(candidate_id) > 120
            or not isinstance(metadata, dict)
        ):
            raise ValueError("A valid candidate ID and metadata dictionary are required.")

        data = self._load()
        if candidate_id in data["candidates"]:
            raise ValueError("Candidate IDs are immutable and cannot be overwritten.")

        data["candidates"][candidate_id] = {
            "metadata": metadata,
            "status": "candidate",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save(data)
        return {"candidate_id": candidate_id, "status": "candidate"}

    def record_evaluation(self, candidate_id, report):
        if not isinstance(report, dict) or report.get("candidate_id") != str(candidate_id):
            raise ValueError("A matching evaluation report is required.")
        data = self._load()
        candidate = data["candidates"].get(str(candidate_id))
        if not candidate:
            raise KeyError(candidate_id)
        passed = report.get("passed") is True

        integrity = report.get("evaluation_integrity")
        fingerprint = report.get("evaluation_dataset_sha256")
        cases = report.get("cases")
        evaluated = report.get("cases_evaluated")
        errors = report.get("errors")

        integrity_valid = (
            isinstance(integrity, dict)
            and integrity.get("approved_cases_only") is True
            and integrity.get("training_overlap_checked") is True
            and integrity.get("dataset_fingerprint_recorded") is True
            and integrity.get("dataset_unchanged_during_evaluation") is True
            and isinstance(fingerprint, str)
            and len(fingerprint) == 64
            and all(c in "0123456789abcdef" for c in fingerprint.lower())
            and isinstance(cases, int) and not isinstance(cases, bool) and cases > 0
            and isinstance(evaluated, int) and not isinstance(evaluated, bool)
            and evaluated == cases
            and isinstance(errors, list) and not errors
        )

        passed = passed and integrity_valid
        candidate["evaluation"] = report
        candidate["status"] = "evaluation_passed" if passed else "evaluation_failed"
        candidate["evaluated_at"] = datetime.now(timezone.utc).isoformat()
        candidate["production_promotion"] = False
        self._save(data)
        return {"candidate_id": str(candidate_id), "status": candidate["status"],
                "production_model_changed": False}

    def promote(self, candidate_id, human_approval=False, evaluation_passed=False):
        data = self._load()
        if data.get("automatic_promotion"):
            raise PermissionError("Automatic promotion is prohibited.")
        if not data.get("manual_promotion_enabled"):
            raise PermissionError("Manual production promotion is disabled in registry policy.")
        if human_approval is not True or evaluation_passed is not True:
            raise PermissionError("Explicit human approval and a passing evaluation are required.")
        candidate = data["candidates"].get(candidate_id)
        if not candidate:
            raise KeyError(candidate_id)

        report = candidate.get("evaluation", {})
        integrity = report.get("evaluation_integrity", {})
        if (
            candidate.get("status") != "evaluation_passed"
            or report.get("passed") is not True
            or integrity.get("approved_cases_only") is not True
            or integrity.get("training_overlap_checked") is not True
            or integrity.get("dataset_fingerprint_recorded") is not True
            or integrity.get("dataset_unchanged_during_evaluation") is not True
            or not isinstance(report.get("evaluation_dataset_sha256"), str)
            or len(report["evaluation_dataset_sha256"]) != 64
            or report.get("cases", 0) <= 0
            or report.get("cases_evaluated") != report.get("cases")
            or report.get("errors") != []
        ):
            raise PermissionError(
                "Candidate has no complete, integrity-validated passing evaluation."
            )

        previous = data.get("active_model")
        data["history"].append({
            "previous": previous,
            "new": candidate_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        data["active_model"] = candidate_id
        candidate["status"] = "active"
        self._save(data)
        return {"active_model": candidate_id, "previous_model": previous}

    def rollback(self, human_approval=False):
        if human_approval is not True:
            raise PermissionError("Rollback requires explicit human approval.")
        data = self._load()
        if not data["history"]:
            raise RuntimeError("No previous model version is available.")
        previous = data["history"][-1]["previous"]
        if previous is None:
            raise RuntimeError("No prior active model is recorded.")
        current = data.get("active_model")
        data["active_model"] = previous
        data["history"].append({
            "previous": current,
            "new": previous,
            "rollback": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        self._save(data)
        return {"active_model": previous, "rolled_back_from": current}
