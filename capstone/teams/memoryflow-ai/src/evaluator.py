"""Evaluation mode for MemoryFlow AI."""


class Evaluator:
    """Compute lightweight metrics from stored memories."""

    def __init__(self, memory_store):
        self.memory_store = memory_store
        self.run_count = 0

    def evaluate(self):
        """Return automatic evaluation metrics."""
        self.run_count += 1
        memories = self.memory_store.load_memories()
        interactions = [memory for memory in memories if memory.get("type") == "interaction"]
        facts = [memory for memory in memories if memory.get("type") == "fact"]
        protected = [memory for memory in memories if memory.get("status") == "protected"]

        recall_checks = [memory for memory in interactions if self._is_memory_question(memory.get("user_input", ""))]
        recall_hits = [memory for memory in recall_checks if memory.get("replayed_memories")]
        replay_successes = [memory for memory in interactions if memory.get("replayed_memories")]
        judge_scores = [memory.get("judge_result", {}).get("score", 0) for memory in interactions]
        retry_count = sum(1 for memory in interactions if memory.get("judge_result", {}).get("retry_count", 0) > 0)

        memory_recall_accuracy = self._percent(len(recall_hits), len(recall_checks))
        replay_success_rate = self._percent(len(replay_successes), len(interactions))
        average_judge_score = round(sum(judge_scores) / len(judge_scores), 2) if judge_scores else 0
        retry_rate = self._percent(retry_count, len(interactions))
        protected_retention = self._percent(len(protected), len([fact for fact in facts if fact.get("importance", 1) >= 8]))

        result = {
            "memory_recall_accuracy": memory_recall_accuracy,
            "replay_success_rate": replay_success_rate,
            "average_judge_score": average_judge_score,
            "retry_rate": retry_rate,
            "protected_memory_retention": protected_retention,
            "evaluation_run_count": self.run_count,
        }
        self.memory_store.record_evaluation_run()
        return result

    def format_result(self, result):
        """Format evaluation result for console output."""
        return (
            "[EVAL RESULT]\n\n"
            f"Memory Recall Accuracy: {result['memory_recall_accuracy']}%\n"
            f"Replay Success Rate: {result['replay_success_rate']}%\n"
            f"Average Judge Score: {result['average_judge_score']}\n"
            f"Retry Rate: {result['retry_rate']}%\n"
            f"Protected Memory Retention: {result['protected_memory_retention']}%\n"
            f"Evaluation Run Count: {result['evaluation_run_count']}"
        )

    def _is_memory_question(self, text):
        text = str(text)
        if any(pattern in text for pattern in ["내 이름은", "내 프로젝트는", "내 캡스톤 주제는", "나는 "]):
            return False
        return any(term in text for term in ["이름", "프로젝트", "캡스톤", "기억", "뭘 만들", "요즘"])

    def _percent(self, numerator, denominator):
        if denominator == 0:
            return 100
        return round((numerator / denominator) * 100, 1)
