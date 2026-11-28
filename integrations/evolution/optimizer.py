
import json
from pathlib import Path
from datetime import datetime, timezone

class DSPyOptimizer:
    def __init__(self, root="data/intelligence/evolution/optimized_candidates"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def optimize(self, program, metric, curated_dataset, candidate_id, max_demos=4, example_adapter=None):
        if not callable(metric):
            raise TypeError("A callable DSPy metric is required.")
        if not curated_dataset:
            raise RuntimeError("No curated learning examples available.")

        import dspy

        examples = []
        if example_adapter is not None and not callable(example_adapter):
            raise TypeError("example_adapter must be callable.")

        for row in curated_dataset:
            if not isinstance(row, dict) or row.get("curated") is not True:
                continue

            human_approved = (
                row.get("approved") is True
                and row.get("curation_method") == "human_approved"
            )
            provenance = row.get("provenance", {})
            autonomous_verified = (
                row.get("approved") is False
                and row.get("curation_method") == "autonomous_verified"
                and isinstance(provenance, dict)
                and provenance.get("semantic_success_verified") is True
                and provenance.get("trusted_source") is True
                and provenance.get("tool_execution_success") is True
            )
            if not (human_approved or autonomous_verified):
                continue

            if example_adapter is not None:
                example = example_adapter(row, dspy)
                if example is not None:
                    examples.append(example)
                continue

            inputs = row.get("task")
            outcome = row.get("outcome")
            if autonomous_verified:
                if not isinstance(outcome, dict):
                    continue
                expected = outcome.get("verified_learning_target")
                if not isinstance(expected, dict) or not expected:
                    continue
            else:
                expected = outcome

            if expected is None:
                continue
            if isinstance(inputs, str):
                inputs = {"question": inputs}
            if not isinstance(inputs, dict) or not inputs:
                continue
            examples.append(
                dspy.Example(**inputs, expected=expected).with_inputs(*inputs.keys())
            )

        if not examples:
            raise RuntimeError("No valid curated examples found.")

        optimizer = dspy.BootstrapFewShot(
            metric=metric,
            max_bootstrapped_demos=max(1, min(int(max_demos), 8))
        )
        optimized = optimizer.compile(program, trainset=examples)

        safe_id = "".join(c for c in str(candidate_id) if c.isalnum() or c in "-_")[:80]
        if not safe_id:
            raise ValueError("Invalid candidate ID.")

        target = self.root / safe_id
        target.mkdir(parents=True, exist_ok=True)
        artifact = target / "program.json"
        optimized.save(str(artifact))

        metadata = {
            "candidate_id": safe_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "optimizer": "BootstrapFewShot",
            "training_examples": len(examples),
            "artifact": str(artifact),
            "production_promotion": False
        }
        (target / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        return {"optimized": True, **metadata, "_program_object": optimized}
