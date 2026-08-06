"""Console entry point for MemoryFlow AI."""

import json

from config import MAX_RETRIES, TOKEN_LIMIT
from context_manager import ContextManager
from evaluator import Evaluator
from intent_analyzer import IntentAnalyzer
from judge import Judge
from memory_gate import MemoryGate
from memory_store import MemoryStore
from reflection_manager import ReflectionManager
from replay_engine import ReplayEngine
from response_generator import ResponseGenerator
from retry_policy import RetryPolicy
from token_monitor import TokenMonitor


DEMO_INPUTS = [
    "내 이름은 현우야",
    "나는 Unity 게임을 만들고 있어",
    "내 캡스톤 주제는 MemoryFlow AI야",
    "내가 요즘 뭘 만들고 있었지?",
    "내 캡스톤 주제가 뭐야?",
    "show memory",
    "stats",
]


def run_turn(user_input, messages, components):
    """Run one full closed-loop turn and return the final AI response."""
    intent_analyzer = components["intent_analyzer"]
    token_monitor = components["token_monitor"]
    context_manager = components["context_manager"]
    memory_gate = components["memory_gate"]
    replay_engine = components["replay_engine"]
    response_generator = components["response_generator"]
    judge = components["judge"]
    retry_policy = components["retry_policy"]
    memory_store = components["memory_store"]
    reflection_manager = components["reflection_manager"]
    conflict_resolver = components["conflict_resolver"]

    trace = []

    intent = intent_analyzer.analyze(user_input)
    print(f"\n[INTENT]: {intent['intent']} / {intent['target']}")
    trace.append(f"IntentAnalyzer -> {intent['intent']}/{intent['target']}")

    use_memory = memory_gate.should_use_memory(intent, user_input)
    print("\n[MEMORY GATE]")
    print(f"use_memory={use_memory}")
    trace.append(f"MemoryGate -> use_memory={use_memory}")

    messages.append({"role": "user", "content": user_input})
    token_count = token_monitor.estimate_conversation_tokens(messages)
    print(f"[TOKEN COUNT]: {token_count}")
    trace.append(f"TokenMonitor -> {token_count} tokens")

    if use_memory:
        memories = memory_store.load_memories()
        protected_before = memory_store.lifecycle.protect_important_memories(memories)
        memory_store.save_memories(memories)
        trace.append(f"LifecycleManager -> protected {protected_before} memories before replay")
    else:
        replay_engine.last_scores = []
        trace.append("LifecycleManager -> skipped before replay")

    if token_count > TOKEN_LIMIT:
        compressed = context_manager.compress_context(messages)
        print("[CONTEXT COMPRESSION]: enabled")
        if compressed.get("summary"):
            print(f"[SUMMARY]: {compressed['summary']}")
    else:
        context_manager.compress_context(messages)

    if use_memory:
        replayed_memories = replay_engine.replay(user_input, intent)
        score_block = replay_engine.format_retrieval_scores()
        if score_block:
            print(f"\n{score_block}")
        trace.append(f"RetrievalScorer -> {len(replay_engine.last_scores)} memories scored for replay")

        replay_block = replay_engine.format_replay_block(replayed_memories)
        if replay_block:
            print(f"\n{replay_block}")
        trace.append(f"ReplayAgent -> {len(replayed_memories)} memories replayed")
    else:
        replayed_memories = []
        trace.append("RetrievalScorer -> skipped by memory gate")
        trace.append("ReplayAgent -> skipped by memory gate")

    response = response_generator.generate_response(user_input, replayed_memories, intent)
    trace.append("ResponseGenerator -> response generated")
    judge_result = judge.evaluate(user_input, response, replayed_memories, intent, use_memory=use_memory)
    judge_result["retry_count"] = 0
    trace.append(f"JudgeAgent -> {'passed' if judge_result.get('passed') else 'failed'}, score {judge_result.get('score')}")

    retry_count = 0
    while retry_policy.should_retry(judge_result, retry_count):
        retry_count += 1
        retry_prompt = retry_policy.build_retry_prompt(user_input, judge_result, replayed_memories, intent)
        print(f"\n[RETRY {retry_count}]")
        print(retry_prompt)
        response = response_generator.generate_response(user_input, replayed_memories, intent)
        judge_result = judge.evaluate(user_input, response, replayed_memories, intent, use_memory=use_memory)
        judge_result["retry_count"] = retry_count

    trace.append(f"RetryPolicy -> {'no retry' if retry_count == 0 else str(retry_count) + ' retries'}")

    if use_memory:
        reflection = reflection_manager.reflect(user_input, intent, judge_result, replayed_memories)
    else:
        reflection = None

    if reflection:
        trace.append("ReflectionManager -> reflection memory saved")
    elif use_memory:
        trace.append("ReflectionManager -> no reflection needed")
    else:
        trace.append("ReflectionManager -> skipped by memory gate")

    print(f"\nAI:\n{response}")
    print("\n[JUDGE]:")
    print(json.dumps(judge_result, ensure_ascii=False, indent=2))

    messages.append({"role": "assistant", "content": response})
    conflicts = memory_store.save_interaction(user_input, response, replayed_memories, judge_result)
    trace.append("MemoryStore -> saved final interaction")

    for conflict in conflicts:
        print()
        print(conflict_resolver.format_conflict(conflict))

    memory_store.summarize_recent_interactions()
    if use_memory:
        memories = memory_store.load_memories()
        protected_after = memory_store.lifecycle.protect_important_memories(memories)
        memory_store.save_memories(memories)
        trace.append(f"LifecycleManager -> protected {protected_after} memories after update")
    else:
        trace.append("LifecycleManager -> skipped after update")

    print_agent_trace(trace)
    return response


def print_agent_trace(trace):
    """Print one concise trace block for the completed turn."""
    print("\n[AGENT TRACE]")
    for item in trace:
        print(item)


def print_memory_stats(messages, components):
    """Print memory and context statistics."""
    memory_store = components["memory_store"]
    token_monitor = components["token_monitor"]
    context_manager = components["context_manager"]

    memory_stats = memory_store.get_statistics()
    context_stats = context_manager.get_statistics()
    token_count = token_monitor.estimate_conversation_tokens(messages)

    print("\n[MEMORY STATS]")
    print(f"Total Memories: {memory_stats['total']}")
    print(f"Fact Memories: {memory_stats['fact']}")
    print(f"Summary Memories: {memory_stats['summary']}")
    print(f"Reflection Memories: {memory_stats['reflection']}")
    print(f"Interaction Memories: {memory_stats['interaction']}")
    print(f"Protected Memories: {memory_stats['protected']}")
    print(f"Active Memories: {memory_stats['active']}")
    print(f"Archived Memories: {memory_stats['archived']}")
    print(f"Compressed Memories: {memory_stats['compressed']}")
    print(f"Total Replay Access Count: {memory_stats['total_replay_access_count']}")
    print(f"Conflict Count: {memory_stats['conflict_count']}")
    print(f"Average Retrieval Score: {memory_stats['average_retrieval_score']}")
    print(f"Replay Success Count: {memory_stats['replay_success_count']}")
    print(f"Evaluation Run Count: {memory_stats['evaluation_run_count']}")
    print(f"Compressed Contexts: {context_stats['compressed_context_count']}")
    print(f"Token Count: {token_count}")


def handle_command(user_input, messages, components):
    """Handle non-chat commands. Return True if a command was handled."""
    intent = components["intent_analyzer"].analyze(user_input)
    command = intent["intent"]
    raw = user_input.lower().strip()

    if command == "exit":
        print("MemoryFlow AI를 종료합니다.")
        return "exit"
    if command == "command_stats":
        print_memory_stats(messages, components)
        return True
    if command == "command_show_memory":
        print()
        print(components["memory_store"].format_all_memories())
        return True
    if command == "command_demo":
        run_demo(messages, components)
        return True
    if raw == "eval":
        result = components["evaluator"].evaluate()
        print()
        print(components["evaluator"].format_result(result))
        return True
    return False


def run_demo(messages, components):
    """Run a built-in presentation demo."""
    print("\n[DEMO START]")
    for item in DEMO_INPUTS:
        print(f"\nUser: {item}")
        handled = handle_command(item, messages, components)
        if not handled:
            run_turn(item, messages, components)
    print("\n[DEMO END]")


def build_components():
    """Create all components used by the MemoryFlow AI loop."""
    memory_store = MemoryStore()
    context_manager = ContextManager(memory_store=memory_store)
    return {
        "intent_analyzer": IntentAnalyzer(),
        "memory_gate": MemoryGate(),
        "token_monitor": TokenMonitor(),
        "context_manager": context_manager,
        "memory_store": memory_store,
        "conflict_resolver": memory_store.conflict_resolver,
        "lifecycle_manager": memory_store.lifecycle,
        "replay_engine": ReplayEngine(memory_store=memory_store),
        "response_generator": ResponseGenerator(),
        "judge": Judge(),
        "retry_policy": RetryPolicy(MAX_RETRIES),
        "reflection_manager": ReflectionManager(memory_store),
        "evaluator": Evaluator(memory_store),
    }


def main():
    """Start an interactive console session."""
    print("MemoryFlow AI")
    print("명령어: demo, eval, stats, show memory, exit, quit")

    messages = []
    components = build_components()

    while True:
        user_input = input("\nUser: ").strip()
        if not user_input:
            continue

        handled = handle_command(user_input, messages, components)
        if handled == "exit":
            break
        if handled:
            continue

        run_turn(user_input, messages, components)


if __name__ == "__main__":
    main()
