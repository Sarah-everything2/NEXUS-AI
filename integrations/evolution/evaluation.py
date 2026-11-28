
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from statistics import mean

class EvaluationEngine:
    def __init__(self, root="data/intelligence/evolution"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.dataset = self.root / "evaluation_dataset.jsonl"
        self.reports = self.root / "evaluation_reports"
        self.reports.mkdir(parents=True, exist_ok=True)

    def add_case(self, inputs, expected, approved=False, provenance=None):
        if approved is not True:
            raise PermissionError("Explicit approval is required to introduce a new evaluation case.")
        if not isinstance(inputs, dict) or not inputs:
            raise TypeError("Inputs must be a non-empty dictionary.")
        if not isinstance(provenance or {}, dict) or not provenance:
            raise TypeError("Evaluation provenance must be a non-empty dictionary.")
        from .governance import redact
        record = {
            "inputs": redact(inputs),
            "expected": redact(expected),
            "provenance": redact(provenance or {}),
            "approved": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        with self.dataset.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return {"saved": True}

    @staticmethod
    def _case_fingerprint(inputs, expected):
        import hashlib
        payload = json.dumps(
            {"inputs": inputs, "expected": expected},
            sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _identity_values(record):
        values = set()
        provenance = record.get("provenance", {})
        if not isinstance(provenance, dict):
            provenance = {}

        for source in (record, provenance):
            for key in (
                "id", "record_id", "experience_id",
                "source_experience_id", "cycle_id"
            ):
                value = source.get(key)
                if value is not None and str(value).strip():
                    values.add(str(value).strip())
        return values

    def _training_data(self):
        training_path = self.root / "curated_dataset.jsonl"
        if not training_path.exists():
            return [], set(), set()

        records, fingerprints, identities = [], set(), set()

        for line_number, line in enumerate(
            training_path.read_text(encoding="utf-8-sig").splitlines(), 1
        ):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except Exception as exc:
                raise RuntimeError(
                    f"Malformed training record at line {line_number}."
                ) from exc

            if not isinstance(record, dict):
                raise RuntimeError(
                    f"Invalid training record at line {line_number}."
                )

            records.append(record)
            identities.update(self._identity_values(record))

            if isinstance(record.get("inputs"), dict) and "expected" in record:
                fingerprints.add(
                    self._case_fingerprint(
                        record["inputs"], record["expected"]
                    )
                )

        return records, fingerprints, identities

    def load_cases(self):
        if not self.dataset.exists():
            return []

        _, training_fingerprints, training_identities = self._training_data()
        cases, seen_fingerprints = [], set()

        for line_number, line in enumerate(
            self.dataset.read_text(encoding="utf-8-sig").splitlines(), 1
        ):
            if not line.strip():
                continue

            try:
                case = json.loads(line)
            except Exception as exc:
                raise RuntimeError(
                    f"Malformed evaluation case at line {line_number}."
                ) from exc

            if not isinstance(case, dict):
                raise RuntimeError(
                    f"Invalid evaluation case at line {line_number}."
                )

            if case.get("approved") is not True:
                continue

            inputs = case.get("inputs")
            provenance = case.get("provenance")

            if not isinstance(inputs, dict) or not inputs:
                raise RuntimeError(
                    f"Evaluation case {line_number} has invalid inputs."
                )
            if "expected" not in case:
                raise RuntimeError(
                    f"Evaluation case {line_number} has no expected output."
                )
            if not isinstance(provenance, dict) or not provenance:
                raise RuntimeError(
                    f"Evaluation case {line_number} has no provenance."
                )

            fingerprint = self._case_fingerprint(
                inputs, case["expected"]
            )

            if fingerprint in seen_fingerprints:
                raise RuntimeError(
                    f"Duplicate evaluation case detected at line {line_number}."
                )
            if fingerprint in training_fingerprints:
                raise RuntimeError(
                    f"Training/evaluation data leakage detected at line {line_number}."
                )

            shared_ids = (
                self._identity_values(case) & training_identities
            )
            if shared_ids:
                raise RuntimeError(
                    f"Evaluation case shares a training record identifier at line {line_number}."
                )

            seen_fingerprints.add(fingerprint)
            cases.append(case)

        return cases

    def compare(self, candidate_id, baseline_predictor, candidate_predictor,
                metric, minimum_score=0.75, maximum_regression=0.02):
        import math

        if (
            isinstance(minimum_score, bool)
            or not isinstance(minimum_score, (int, float))
            or not math.isfinite(minimum_score)
            or not 0 <= minimum_score <= 1
        ):
            raise ValueError("minimum_score must be a finite number between 0 and 1.")

        if (
            isinstance(maximum_regression, bool)
            or not isinstance(maximum_regression, (int, float))
            or not math.isfinite(maximum_regression)
            or not 0 <= maximum_regression <= 1
        ):
            raise ValueError("maximum_regression must be a finite number between 0 and 1.")

        if not callable(metric) or not callable(baseline_predictor) or not callable(candidate_predictor):
            raise TypeError("Evaluation predictors and metric must be callable.")

        initial_dataset_bytes = (
            self.dataset.read_bytes() if self.dataset.exists() else b""
        )
        initial_dataset_fingerprint = hashlib.sha256(
            initial_dataset_bytes
        ).hexdigest()

        cases = self.load_cases()

        current_dataset_bytes = (
            self.dataset.read_bytes() if self.dataset.exists() else b""
        )
        if hashlib.sha256(current_dataset_bytes).hexdigest() != initial_dataset_fingerprint:
            raise RuntimeError("Evaluation dataset changed while cases were loading.")

        if not cases:
            raise RuntimeError("No approved evaluation cases available.")

        base_scores, candidate_scores, errors = [], [], []

        for index, case in enumerate(cases):
            try:
                expected, inputs = case["expected"], case["inputs"]
                raw_base = metric(expected, baseline_predictor(**inputs))
                raw_candidate = metric(expected, candidate_predictor(**inputs))

                if isinstance(raw_base, bool) or isinstance(raw_candidate, bool):
                    raise ValueError("Evaluation metric must return numeric scores, not booleans.")

                base = float(raw_base)
                candidate = float(raw_candidate)

                if (
                    not math.isfinite(base)
                    or not math.isfinite(candidate)
                    or not (0 <= base <= 1 and 0 <= candidate <= 1)
                ):
                    raise ValueError("Evaluation metric must return finite scores between 0 and 1.")

                base_scores.append(base)
                candidate_scores.append(candidate)
            except Exception as exc:
                errors.append({
                    "case": index,
                    "error": str(exc)[:300]
                })

        final_dataset_bytes = (
            self.dataset.read_bytes() if self.dataset.exists() else b""
        )
        final_dataset_fingerprint = hashlib.sha256(
            final_dataset_bytes
        ).hexdigest()

        dataset_unchanged = (
            final_dataset_fingerprint == initial_dataset_fingerprint
        )
        if not dataset_unchanged:
            errors.append({
                "case": "dataset_integrity",
                "error": "Evaluation dataset changed during candidate evaluation."
            })

        base_avg = mean(base_scores) if base_scores else 0.0
        candidate_avg = mean(candidate_scores) if candidate_scores else 0.0

        passed = (
            dataset_unchanged
            and not errors
            and len(candidate_scores) == len(cases)
            and candidate_avg >= minimum_score
            and candidate_avg >= base_avg - maximum_regression
        )

        dataset_fingerprint = initial_dataset_fingerprint

        report = {
            "report_version": 2,
            "candidate_id": str(candidate_id),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "evaluation_dataset": str(self.dataset),
            "evaluation_dataset_sha256": dataset_fingerprint,
            "cases": len(cases),
            "cases_evaluated": len(candidate_scores),
            "baseline_score": round(base_avg, 6),
            "candidate_score": round(candidate_avg, 6),
            "improvement": round(candidate_avg - base_avg, 6),
            "passed": passed,
            "errors": errors,
            "evaluation_integrity": {
                "approved_cases_only": True,
                "training_overlap_checked": True,
                "dataset_fingerprint_recorded": True,
                "dataset_unchanged_during_evaluation": dataset_unchanged
            },
            "production_promotion": False
        }

        safe_id = "".join(c for c in str(candidate_id) if c.isalnum() or c in "-_")[:80]
        if not safe_id:
            raise ValueError("Invalid candidate ID.")
        filename = safe_id + "_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f") + ".json"
        report_path = self.reports / filename
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        report["report_path"] = str(report_path)
        return report
