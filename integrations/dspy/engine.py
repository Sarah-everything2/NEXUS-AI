import asyncio
import json
import logging
from pathlib import Path

logger = logging.getLogger("nexus.dspy")

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config" / "intelligence_stack.json"
STORE = ROOT / "data" / "intelligence" / "dspy"


class DSPyEngine:
    """Optional DSPy intelligence engine using the existing Ollama service."""

    def __init__(self):
        self.dspy = None
        self.lm = None
        self.predictors = {}
        self.config = self._load_config()

    def _load_config(self):
        defaults = {
            "enabled": False,
            "provider": "ollama",
            "optimization_enabled": False,
            "automatic_promotion": False,
            "model": None,
            "timeout": 180,
            "max_retries": 1,
            "evaluation_threshold": 0.85
        }

        if CONFIG.exists():
            try:
                with CONFIG.open("r", encoding="utf-8-sig") as f:
                    defaults.update(json.load(f))
            except (OSError, ValueError):
                logger.exception("Could not load DSPy configuration.")

        return defaults

    def initialize(self):
        if not self.config.get("enabled", False):
            return False

        if self.dspy is not None:
            return True

        try:
            import dspy
            from core.settings import load_settings

            settings = load_settings()
            model = self.config.get("model") or settings.get("model")

            if not model:
                raise ValueError("No Ollama model configured.")

            base_url = settings["ollama_url"].rstrip("/")

            self.dspy = dspy
            self.lm = dspy.LM(
                model=f"ollama_chat/{model}",
                api_base=base_url,
                api_key="ollama",
                timeout=self.config.get("timeout", 180),
                num_retries=self.config.get("max_retries", 1)
            )

            STORE.mkdir(parents=True, exist_ok=True)
            return True

        except Exception:
            logger.exception("DSPy initialization failed.")
            self.dspy = None
            self.lm = None
            return False

    def _predict(self, signature, **inputs):
        if not self.initialize():
            raise RuntimeError("DSPy is disabled or unavailable.")

        predictor = self.dspy.Predict(signature)

        with self.dspy.context(lm=self.lm):
            return predictor(**inputs)

    def build_reasoning_program(self):
        """Build a reusable DSPy reasoning module without enabling DSPy."""
        if self.config.get("enabled") is not True:
            raise PermissionError("DSPy is disabled in intelligence_stack.json.")
        if self.config.get("optimization_enabled") is not True:
            raise PermissionError("DSPy optimization is disabled in intelligence_stack.json.")
        if not self.initialize():
            raise RuntimeError("DSPy initialization failed.")

        from .signatures import ReasoningSignature
        if ReasoningSignature is None:
            raise RuntimeError("DSPy reasoning signature is unavailable.")

        engine = self
        dspy = self.dspy

        class ContextualReasoner(dspy.Module):
            def __init__(self):
                super().__init__()
                self.predictor = dspy.Predict(ReasoningSignature)

            def forward(self, question, context=""):
                with dspy.context(lm=engine.lm):
                    return self.predictor(
                        question=question,
                        context=context
                    )

        return ContextualReasoner()

    @staticmethod
    def reasoning_metric(example, prediction, trace=None):
        """Deterministic answer metric; never uses an LLM as its own judge."""
        import re
        expected = getattr(example, "answer", None)
        actual = getattr(prediction, "answer", None)
        if not isinstance(expected, str) or not isinstance(actual, str):
            return 0.0
        normalize = lambda value: " ".join(
            re.sub(r"[^a-z0-9 ]", " ", value.lower()).split()
        )
        return 1.0 if normalize(expected) and normalize(expected) == normalize(actual) else 0.0

    @staticmethod
    def reasoning_example_adapter(row, dspy):
        """Accept only human-curated examples matching ReasoningSignature."""
        if not isinstance(row, dict):
            return None
        if row.get("approved") is not True:
            return None
        if row.get("curation_method") != "human_approved":
            return None

        task = row.get("task")
        outcome = row.get("outcome")
        if not isinstance(task, dict) or not isinstance(outcome, dict):
            return None

        question = task.get("question")
        context = task.get("context")
        analysis = outcome.get("analysis")
        answer = outcome.get("answer")
        confidence = outcome.get("confidence")

        fields = (question, context, analysis, answer, confidence)
        if not all(isinstance(value, str) for value in fields):
            return None
        if not question.strip() or not answer.strip():
            return None

        return dspy.Example(
            question=question,
            context=context,
            analysis=analysis,
            answer=answer,
            confidence=confidence
        ).with_inputs("question", "context")

    def reason(self, question, context=""):
        from .signatures import ReasoningSignature

        result = self._predict(
            ReasoningSignature,
            question=question,
            context=context
        )

        return {
            "analysis": result.analysis,
            "answer": result.answer,
            "confidence": result.confidence
        }

    def plan(self, question, available_tools):
        from .signatures import PlanningSignature

        result = self._predict(
            PlanningSignature,
            question=question,
            available_tools=json.dumps(available_tools)
        )

        return {
            "reasoning": result.reasoning,
            "actions_json": result.actions_json
        }

    def evaluate(self, task, expected, actual):
        from .signatures import EvaluationSignature

        result = self._predict(
            EvaluationSignature,
            task=task,
            expected=expected,
            actual=actual
        )

        return {
            "score": result.score,
            "feedback": result.feedback
        }

    async def areason(self, question, context=""):
        return await asyncio.to_thread(
            self.reason, question, context
        )

    async def aplan(self, question, available_tools):
        return await asyncio.to_thread(
            self.plan, question, available_tools
        )

    async def aevaluate(self, task, expected, actual):
        return await asyncio.to_thread(
            self.evaluate, task, expected, actual
        )

    def save_candidate(self, name, content, evaluation):
        """Save an evaluated candidate without promoting it."""
        STORE.mkdir(parents=True, exist_ok=True)

        record = {
            "name": name,
            "content": content,
            "evaluation": evaluation,
            "status": "candidate",
            "requires_human_approval": True
        }

        path = STORE / f"{name}.json"
        temporary = path.with_suffix(".tmp")

        temporary.write_text(
            json.dumps(record, indent=2),
            encoding="utf-8"
        )
        temporary.replace(path)

        return str(path)
