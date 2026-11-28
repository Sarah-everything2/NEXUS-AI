
import json
from datetime import datetime, timezone
from pathlib import Path
from .experience_store import ExperienceStore
from .registry import ModelRegistry
from .evaluation import EvaluationEngine
from .optimizer import DSPyOptimizer
import uuid

class EvolutionEngine:
    def __init__(self):
        self.experiences = ExperienceStore()
        self.registry = ModelRegistry()
        self.evaluation = EvaluationEngine()
        self.optimizer = DSPyOptimizer()
        self.policy_path = Path("config/autonomy_policy.json")

    def _dspy_optimization_enabled(self):
        """Require both autonomy policy and explicit DSPy configuration."""
        policy = self._policy()
        autonomy = policy.get("autonomy", {})
        config_path = Path("config/intelligence_stack.json")

        if not config_path.exists():
            return False

        try:
            config = json.loads(config_path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError, TypeError):
            return False

        return (
            autonomy.get("automatic_dspy_optimization") is True
            and config.get("enabled") is True
            and config.get("optimization_enabled") is True
        )

    def _policy(self):
        return json.loads(self.policy_path.read_text(encoding="utf-8"))

    def record_approved_experience(self, task, outcome, approved=False, provenance=None):
        policy = self._policy()["autonomy"]
        if approved is not True and not policy.get("experience_collection"):
            raise PermissionError("Autonomous experience collection is disabled.")
        # Raw autonomous experiences remain unapproved and cannot train a model.
        return self.experiences.capture(
            task, outcome, approved=bool(approved), provenance=provenance
        )

    def curate_experience(self, record, approved=False, autonomous=False):
        policy = self._policy()

        if approved is True:
            return self.experiences.curate(record, approved=True)

        if autonomous is True:
            autonomy = policy.get("autonomy", {})
            if autonomy.get("automatic_verified_curation") is not True:
                raise PermissionError("Automatic verified curation is disabled.")
            return self.experiences.curate(record, autonomous=True)

        raise PermissionError("Experience curation is not authorized.")

    def curate_latest_verified_experience(self, cycle_id):
        """Curate a persisted verified record only when policy permits."""
        policy = self._policy().get("autonomy", {})
        if policy.get("automatic_verified_curation") is not True:
            return {"curated": False, "reason": "automatic_verified_curation_disabled"}

        record = self.experiences.find_latest(cycle_id)
        if not isinstance(record, dict):
            return {"curated": False, "reason": "experience_record_not_found"}

        result = self.curate_experience(record, autonomous=True)
        return result

    def register_candidate(self, candidate_id, metadata):
        return self.registry.register_candidate(candidate_id, metadata)

    def run_improvement_cycle(
        self, program, metric, max_candidates=1, max_seconds=120,
        max_demos=None, stop_check=None, example_adapter=None
    ):
        """Run one explicitly requested, bounded DSPy improvement cycle.

        Every candidate passes through optimize_candidate(), which performs
        mandatory independent evaluation and registry recording. This method
        never promotes or replaces the production model.
        """
        import time

        policy = self._policy()
        autonomy = policy.get("autonomy", {})
        if not self._dspy_optimization_enabled():
            raise PermissionError(
                "DSPy optimization requires enabled=true and "
                "optimization_enabled=true in config/intelligence_stack.json, "
                "as well as the autonomy policy."
            )

        if not callable(metric):
            raise TypeError("A callable DSPy metric is required.")

        if isinstance(max_candidates, bool) or not isinstance(max_candidates, int):
            raise ValueError("max_candidates must be an integer.")
        if isinstance(max_seconds, bool) or not isinstance(max_seconds, (int, float)):
            raise ValueError("max_seconds must be numeric.")

        configured_limit = autonomy.get("maximum_optimization_candidates", 1)
        if isinstance(configured_limit, bool) or not isinstance(configured_limit, int):
            configured_limit = 1

        candidate_limit = max(1, min(max_candidates, configured_limit, 3))
        time_limit = max(1.0, min(float(max_seconds), 300.0))
        deadline = time.monotonic() + time_limit

        results = []
        stopped = False

        for index in range(candidate_limit):
            if stop_check is not None:
                if not callable(stop_check):
                    raise TypeError("stop_check must be callable.")
                if stop_check():
                    stopped = True
                    break

            if time.monotonic() >= deadline:
                stopped = True
                break

            candidate_id = (
                "dspy-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
                + "-" + uuid.uuid4().hex[:12]
            )

            try:
                candidate = self.optimize_candidate(
                    program=program,
                    metric=metric,
                    candidate_id=candidate_id,
                    max_demos=max_demos,
                    example_adapter=example_adapter,
                )
                results.append({
                    "candidate_id": candidate_id,
                    "success": True,
                    "evaluation_passed": candidate.get("evaluation_passed") is True,
                    "candidate_eligible_for_review": (
                        candidate.get("candidate_eligible_for_review") is True
                    ),
                    "production_model_changed": False,
                    "result": candidate,
                })
            except Exception as exc:
                results.append({
                    "candidate_id": candidate_id,
                    "success": False,
                    "error": str(exc)[:500],
                    "production_model_changed": False,
                })

            if stop_check is not None and stop_check():
                stopped = True
                break

            if time.monotonic() >= deadline and index + 1 < candidate_limit:
                stopped = True
                break

        review_candidates = [
            item["candidate_id"] for item in results
            if item.get("candidate_eligible_for_review") is True
        ]

        return {
            "cycle_completed": not stopped,
            "stopped_or_time_limited": stopped,
            "candidates_attempted": len(results),
            "candidate_limit": candidate_limit,
            "time_limit_seconds": time_limit,
            "results": results,
            "review_candidates": review_candidates,
            "production_model_changed": False,
            "automatic_promotion": False,
        }

    def run_reasoning_improvement_cycle(
        self, dspy_engine, max_candidates=1, max_seconds=120,
        max_demos=None, stop_check=None
    ):
        """Optimize the reusable reasoning program using schema-matched data."""
        if dspy_engine is None:
            raise ValueError("A DSPyEngine instance is required.")
        program = dspy_engine.build_reasoning_program()
        metric = dspy_engine.reasoning_metric
        adapter = dspy_engine.reasoning_example_adapter

        return self.run_improvement_cycle(
            program=program,
            metric=metric,
            max_candidates=max_candidates,
            max_seconds=max_seconds,
            max_demos=max_demos,
            stop_check=stop_check,
            example_adapter=adapter,
        )

    def promote_candidate(self, candidate_id, human_approval=False, evaluation_passed=False):
        raise PermissionError("Production model replacement is disabled by autonomy policy.")

    def rollback(self, human_approval=False):
        return self.registry.rollback(human_approval)

    def add_evaluation_case(self, inputs, expected, approved=False, provenance=None):
        return self.evaluation.add_case(inputs, expected, approved, provenance)

    def evaluate_candidate(self, candidate_id, baseline_predictor, candidate_predictor,
                           metric, minimum_score=None, maximum_regression=None):
        policy = self._policy()["learning"]
        return self.evaluation.compare(
            candidate_id, baseline_predictor, candidate_predictor, metric,
            minimum_score if minimum_score is not None else policy["minimum_evaluation_score"],
            maximum_regression if maximum_regression is not None else policy["maximum_regression"]
        )

    def optimize_candidate(self, program, metric, candidate_id, human_approval=False, max_demos=None, example_adapter=None):
        policy = self._policy()
        if not self._dspy_optimization_enabled():
            raise PermissionError(
                "DSPy optimization is disabled by configuration or autonomy policy."
            )
        dataset = []
        path = self.experiences.dataset
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    provenance = row.get("provenance", {})
                    human_approved = (
                        row.get("approved") is True
                        and row.get("curated") is True
                        and row.get("curation_method") == "human_approved"
                    )
                    autonomous_verified = (
                        row.get("approved") is False
                        and row.get("curated") is True
                        and row.get("curation_method") == "autonomous_verified"
                        and isinstance(provenance, dict)
                        and provenance.get("semantic_success_verified") is True
                        and provenance.get("trusted_source") is True
                        and provenance.get("tool_execution_success") is True
                    )
                    if human_approved or autonomous_verified:
                        dataset.append(row)
        dataset = dataset[:policy["learning"]["maximum_optimization_examples"]]
        if not dataset:
            raise RuntimeError("No approved, curated experiences are available for optimization.")

        result = self.optimizer.optimize(
            program, metric, dataset, candidate_id,
            max_demos=max_demos or policy["learning"]["maximum_bootstrapped_demos"],
            example_adapter=example_adapter
        )

        if not isinstance(result, dict) or result.get("optimized") is not True:
            raise RuntimeError("DSPy optimization did not produce a valid candidate.")

        # Keep the executable candidate separate from serializable registry metadata.
        candidate_program = result.pop("_program_object", None)
        if candidate_program is None:
            raise RuntimeError("Optimizer did not return an executable candidate.")

        metadata = {
            **result,
            "candidate_type": "dspy_optimized_program",
            "training_examples": len(dataset),
            "registered_at": datetime.now().astimezone().isoformat(),
            "production_promotion": False,
            "requires_evaluation": True,
        }
        registration = self.registry.register_candidate(str(candidate_id), metadata)

        # Evaluation is mandatory for every candidate. Configuration cannot
        # silently bypass this quality gate.
        evaluation_error = None
        try:
            evaluation_report = self.evaluate_candidate(
                str(candidate_id), program, candidate_program, metric
            )
        except Exception as exc:
            evaluation_error = str(exc)
            evaluation_report = {
                "candidate_id": str(candidate_id),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "cases": 0,
                "baseline_score": 0.0,
                "candidate_score": 0.0,
                "improvement": 0.0,
                "passed": False,
                "errors": [{
                    "case": "evaluation_setup",
                    "error": evaluation_error,
                }],
                "evaluation_error": True,
                "production_promotion": False,
            }

        evaluation_registry = self.registry.record_evaluation(
            str(candidate_id), evaluation_report
        )

        evaluation_passed = evaluation_report.get("passed") is True

        return {
            **result,
            "registry": registration,
            "evaluation": evaluation_report,
            "evaluation_registry": evaluation_registry,
            "evaluation_required": True,
            "evaluation_passed": evaluation_passed,
            "candidate_eligible_for_review": (
                evaluation_passed
                and evaluation_report.get("evaluation_integrity", {}).get(
                    "training_overlap_checked"
                ) is True
            ),
            "evaluation_error": evaluation_error,
            "production_model_changed": False,
        }
