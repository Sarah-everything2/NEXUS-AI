import asyncio
import inspect
import json
import logging
from pathlib import Path
from datetime import datetime, timezone

log = logging.getLogger("nexus.autonomy")


class AutonomousCoordinator:
    """Coordinates DSPy, Evolution and the existing NEXUS executor."""

    def __init__(self, agent, policy_path="config/autonomy_policy.json"):
        self.agent = agent
        self.policy_path = Path(policy_path)
        self.state_dir = Path("data/intelligence/autonomy")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.audit_file = self.state_dir / "cycles.jsonl"
        self._running = False
        self._cancel_requested = False
        self._active_task = None

    def _policy(self):
        return json.loads(self.policy_path.read_text(encoding="utf-8"))

    def _audit(self, event):
        record = {"timestamp": datetime.now(timezone.utc).isoformat(), **event}
        with self.audit_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\\n")

    async def _call(self, fn, *args, **kwargs):
        value = fn(*args, **kwargs)
        return await value if inspect.isawaitable(value) else value

    def _check_stop(self):
        if self._cancel_requested:
            raise RuntimeError("Autonomous cycle stopped.")
        return True

    async def _execute_existing_tools(self, actions):
        import importlib

        module = importlib.import_module("core.agent")
        safe_tools = set(getattr(module, "AUTONOMOUS_SAFE_TOOLS", ()))

        # Retry only operations that are explicitly safe to repeat.
        retry_safe_tools = {
            "list_files", "read_file", "web_research", "trend_discovery",
            "signal_commander_discover", "signal_commander_dashboard",
            "signal_commander_memory", "signal_commander_insights",
            "signal_commander_report_search", "signal_commander_registry_audit",
            "xmrig_status", "xmrig_health", "xmrig_logs",
            "xmrig_recovery_check", "video_probe",
            "youtube_status", "youtube_channel",
            "x_status", "x_account", "x_analytics",
            "x_search_trends", "x_account_timeline",
            "mt5_get_account", "mt5_get_price", "mt5_get_positions",
            "mt5_get_history", "mt5_get_strategy_signal",
        }

        autonomy = self._policy().get("autonomy", {})
        retries_enabled = autonomy.get("automatic_retry", False) is True
        try:
            maximum_retries = int(autonomy.get("maximum_retries", 0))
        except (TypeError, ValueError):
            maximum_retries = 0
        maximum_retries = max(0, min(maximum_retries, 3))

        results = []
        seen = set()

        for action in actions[:3]:
            self._check_stop()
            if not isinstance(action, dict):
                continue

            tool = action.get("tool")
            args = action.get("arguments", {})
            if tool not in safe_tools or not isinstance(args, dict):
                continue
            if not self.agent._tool_allowed(tool):
                continue

            key = (tool, json.dumps(args, sort_keys=True, default=str))
            if key in seen:
                continue
            seen.add(key)

            retry_limit = (
                maximum_retries
                if retries_enabled and tool in retry_safe_tools
                else 0
            )

            for attempt in range(retry_limit + 1):
                self._check_stop()
                self._audit({
                    "event": "autonomous_tool_attempt",
                    "tool": tool,
                    "attempt": attempt + 1,
                    "maximum_attempts": retry_limit + 1,
                })

                try:
                    value = await self._call(
                        self.agent.use_tool, tool, _autonomous=True, **args
                    )
                    results.append({
                        "tool": tool,
                        "arguments": dict(args),
                        "result": value,
                        "attempts": attempt + 1,
                        "retry_exhausted": False,
                    })
                    break
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    self._audit({
                        "event": "autonomous_tool_attempt_failed",
                        "tool": tool,
                        "attempt": attempt + 1,
                        "error": str(exc)[:500],
                    })

                    if attempt >= retry_limit:
                        results.append({
                            "tool": tool,
                            "error": str(exc)[:500],
                            "attempts": attempt + 1,
                            "retry_exhausted": retry_limit > 0,
                        })
                        break

                    await asyncio.sleep(min(2 ** attempt, 4))
                    self._check_stop()

        def _tool_result_ok(item):
            if not isinstance(item, dict) or "error" in item:
                return False

            value = item.get("result")

            failure_words = (
                "error", "failed", "failure", "denied",
                "cancelled", "canceled", "blocked"
            )

            if isinstance(value, str):
                return not value.strip().lower().startswith(failure_words)

            if isinstance(value, dict):
                status = str(value.get("status", "")).strip().lower()
                if any(word in status for word in failure_words):
                    return False
                if value.get("success") is False:
                    return False

            return True

        execution_success = bool(results) and all(
            _tool_result_ok(item) for item in results
        )

        return {
            "results": results,
            "success": execution_success,
            "successful_tool_calls": sum(
                1 for item in results if _tool_result_ok(item)
            ),
            "failed_tool_calls": sum(
                1 for item in results if not _tool_result_ok(item)
            ),
            "retry_policy": {
                "enabled": retries_enabled,
                "maximum_retries": maximum_retries,
                "retry_only_idempotent_tools": True,
            },
        }

    async def run_cycle(self, task, executor=None):
        if self._running:
            raise RuntimeError("An autonomous cycle is already running.")

        policy = self._policy()
        autonomy = policy.get("autonomy", {})
        if not autonomy.get("autonomous_task_execution", False):
            raise PermissionError("Autonomous task execution is disabled.")
        if not isinstance(task, str) or not task.strip():
            raise ValueError("A non-empty task description is required.")

        self._running = True
        self._cancel_requested = False
        self._active_task = asyncio.current_task()
        cycle_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        result = {
            "cycle_id": cycle_id,
            "task": task,
            "status": "started",
            "executed": False,
            "learning_recorded": False,
            "production_model_changed": False
        }

        try:
            self._audit({"cycle_id": cycle_id, "event": "cycle_started"})
            self._check_stop()
            reasoning = await self._call(self.agent.dspy_reason, task)
            self._check_stop()
            result["reasoning_available"] = reasoning is not None

            plan = await self._call(self.agent.dspy_plan, task)
            self._check_stop()
            if not isinstance(plan, dict):
                raise RuntimeError("DSPy returned an invalid plan.")

            actions = plan.get("actions", [])
            if not isinstance(actions, list) or len(actions) > 3:
                raise ValueError("Invalid plan or action limit exceeded.")

            result["plan"] = plan
            result["planned_actions"] = len(actions)

            if executor is not None:
                raise PermissionError(
                    "Custom executors are disabled; use the existing permission-controlled executor."
                )

            if actions:
                execution = await self._execute_existing_tools(actions)
                self._check_stop()
                result["execution"] = execution
                tool_results = execution.get("results", []) if isinstance(execution, dict) else []
                result["executed"] = bool(tool_results)
                result["execution_completed"] = bool(tool_results)
                result["tool_execution_success"] = execution.get("success", False)
                result["task_success"] = None
                result["semantic_task_success"] = "unverified"
                result["status"] = (
                    "executed_successfully"
                    if execution.get("success")
                    else "executed_with_errors" if tool_results
                    else "no_safe_actions"
                )
            else:
                result["status"] = "completed_without_actions"
                result["task_success"] = None

            execution = result.get("execution")
            if (
                isinstance(execution, dict)
                and execution.get("results")
                and autonomy.get("experience_collection", False)
            ):
                self._check_stop()

                # Semantic verification is independent of tool-call success.
                from .outcome_verifier import outcome_verifiers
                from .filesystem_verifiers import register_filesystem_verifiers

                register_filesystem_verifiers(outcome_verifiers)

                verification = outcome_verifiers.verify_any(
                    task=task,
                    execution=execution
                )
                if not isinstance(verification, dict):
                    verification = {}

                verified = verification.get("verified") is True
                trusted = verification.get("trusted_source") is True
                semantic_verified = (
                    verification.get("semantic_success_verified") is True
                )
                learning_target = verification.get("learning_target")

                # Only the verifier's normalized target can enter a
                # semantically verified learning record.
                outcome = {
                    "execution_status": (
                        "successful"
                        if execution.get("success")
                        else "completed_with_errors"
                    ),
                    "tool_execution_success": bool(
                        execution.get("success", False)
                    ),
                    "semantic_task_success": (
                        "verified" if verified and trusted and semantic_verified
                        else "unverified"
                    )
                }

                if verified and trusted and semantic_verified and isinstance(
                    learning_target, dict
                ):
                    outcome["verified_learning_target"] = learning_target

                capture = await self._call(
                    self.agent.record_learning_experience,
                    task=task,
                    outcome=outcome,
                    approved=False,
                    provenance={
                        "cycle_id": cycle_id,
                        "source": "registered_outcome_verifier" if verified else
                                  "policy_authorized_autonomous_collection",
                        "human_approved": False,
                        "semantic_success_verified": bool(
                            verified and trusted and semantic_verified
                            and isinstance(learning_target, dict)
                        ),
                        "trusted_source": bool(
                            verified and trusted and semantic_verified
                            and isinstance(learning_target, dict)
                        ),
                        "tool_execution_success": bool(
                            execution.get("success", False)
                        ),
                        "verifier": verification.get("verifier", ""),
                        "verification_scope": verification.get("verification_scope", "none")
                    }
                )

                result["outcome_verified"] = bool(
                    verified and trusted and semantic_verified
                    and isinstance(learning_target, dict)
                )
                result["outcome_verifier"] = verification.get("verifier", "")
                result["semantic_task_success"] = (
                    "verified" if result["outcome_verified"] else "unverified"
                )
                result["learning_recorded"] = (
                    isinstance(capture, dict) and bool(capture.get("saved"))
                )
                result["learning_approved"] = False
                result["eligible_for_training"] = False

                # Curation is a separate policy-controlled operation.
                if result["outcome_verified"]:
                    try:
                        self._check_stop()
                        curation = await self._call(
                            self.agent.curate_latest_verified_experience,
                            cycle_id
                        )
                        result["curation"] = curation
                        result["eligible_for_training"] = bool(
                            isinstance(curation, dict)
                            and curation.get("curated") is True
                        )
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        result["curation"] = {
                            "curated": False,
                            "reason": "curation_error",
                            "error": str(exc)[:300]
                        }
                        result["eligible_for_training"] = False
                        self._audit({
                            "cycle_id": cycle_id,
                            "event": "experience_curation_failed",
                            "error": str(exc)[:300]
                        })



            self._audit({
                "cycle_id": cycle_id,
                "event": "cycle_finished",
                "status": result["status"],
                "executed": result["executed"],
                "learning_recorded": result["learning_recorded"]
            })
            return result

        except asyncio.CancelledError:
            self._audit({"cycle_id": cycle_id, "event": "cycle_cancelled"})
            raise
        except Exception as exc:
            self._audit({
                "cycle_id": cycle_id,
                "event": "cycle_failed",
                "error": str(exc)
            })
            raise
        finally:
            self._running = False
            self._active_task = None

    async def evaluate_candidate(self, candidate_id, baseline, candidate, metric):
        policy = self._policy()
        learning = policy.get("learning", {})
        if not policy.get("autonomy", {}).get("automatic_candidate_evaluation", False):
            raise PermissionError("Automatic evaluation is disabled.")
        self._check_stop()
        report = await self._call(
            self.agent.evaluate_learning_candidate,
            candidate_id, baseline, candidate, metric,
            minimum_score=learning.get("minimum_evaluation_score", 0.75),
            maximum_regression=learning.get("maximum_regression", 0.02)
        )
        self._audit({
            "event": "candidate_evaluated",
            "candidate_id": candidate_id,
            "passed": report.get("passed", False),
            "production_promotion": False
        })
        return report

    async def optimize_candidate(self, program, metric, candidate_id):
        policy = self._policy()
        learning = policy.get("learning", {})
        if not policy.get("autonomy", {}).get("automatic_dspy_optimization", False):
            raise PermissionError("Automatic optimization is disabled.")
        self._check_stop()
        result = await self._call(
            self.agent.optimize_learning_candidate,
            program, metric, candidate_id,
            max_demos=learning.get("maximum_bootstrapped_demos", 4)
        )
        self._audit({
            "event": "candidate_optimized",
            "candidate_id": candidate_id,
            "production_promotion": False
        })
        return result

    def stop(self):
        self._cancel_requested = True
        active = self._active_task
        if active is not None and not active.done():
            active.cancel()
        self._audit({
            "event": "autonomous_stop_requested",
            "active_cycle": active is not None
        })
        return {
            "stopped": True,
            "cancellation_requested": active is not None
        }
