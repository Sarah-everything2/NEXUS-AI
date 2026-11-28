try:
    import dspy
except ImportError:
    dspy = None


if dspy is not None:

    class ReasoningSignature(dspy.Signature):
        """Analyze a request and produce a grounded response."""

        question: str = dspy.InputField()
        context: str = dspy.InputField()
        analysis: str = dspy.OutputField()
        answer: str = dspy.OutputField()
        confidence: str = dspy.OutputField()

    class PlanningSignature(dspy.Signature):
        """Plan safe actions using only explicitly available tools."""

        question: str = dspy.InputField()
        available_tools: str = dspy.InputField()
        reasoning: str = dspy.OutputField()
        actions_json: str = dspy.OutputField(
            desc='JSON object containing an actions list.'
        )

    class EvaluationSignature(dspy.Signature):
        """Evaluate a task result against its expected outcome."""

        task: str = dspy.InputField()
        expected: str = dspy.InputField()
        actual: str = dspy.InputField()
        score: float = dspy.OutputField(
            desc="Score between 0.0 and 1.0."
        )
        feedback: str = dspy.OutputField()

else:
    ReasoningSignature = None
    PlanningSignature = None
    EvaluationSignature = None
