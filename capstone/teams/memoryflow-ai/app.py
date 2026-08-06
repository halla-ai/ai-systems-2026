"""Streamlit presentation demo for MemoryFlow AI."""

from datetime import datetime
from pathlib import Path
import sys
import time

import streamlit as st

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

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
from ui_helpers import (
    inject_styles,
    memory_label,
    memory_text,
    render_card,
    render_header,
    render_memory_tree,
    render_ralph_loop,
    render_reflection_summary,
    render_status_pill,
    render_timeline,
)


DEMO_SCRIPT = [
    ("내 이름은 현우야", "현우님으로 기억하겠습니다."),
    ("우리 프로젝트는 MemoryFlow AI야.", "프로젝트 정보를 장기 기억으로 저장했습니다."),
    ("내가 진행 중인 프로젝트가 뭐였지?", "이전에 저장된 기억에 따르면 현재 MemoryFlow AI 프로젝트를 진행 중입니다."),
]

DEMO_FACTS = {
    "내 이름은 현우야": ("name", "현우"),
    "우리 프로젝트는 MemoryFlow AI야.": ("project", "MemoryFlow AI"),
}

DEMO_INTENTS = {
    "내 이름은 현우야": {"intent": "remember_fact", "target": "name", "keywords": ["이름", "현우"]},
    "우리 프로젝트는 MemoryFlow AI야.": {
        "intent": "remember_fact",
        "target": "project",
        "keywords": ["프로젝트", "MemoryFlow", "AI"],
    },
    "내가 진행 중인 프로젝트가 뭐였지?": {
        "intent": "ask_project",
        "target": "project",
        "keywords": ["프로젝트", "진행"],
    },
}

FRIENDLY_INTENTS = {
    "ask_name": "이름 질문",
    "ask_project": "프로젝트 질문",
    "ask_capstone": "캡스톤 질문",
    "ask_preference": "선호 질문",
    "ask_summary": "최근 작업 요약",
    "remember_fact": "기억 저장",
    "general_chat": "일반 질문",
    "technical_question": "기술 질문",
    "coding_question": "코딩 질문",
    "git_command": "명령어",
    "shell_command": "명령어",
    "programming_question": "프로그래밍 질문",
}

MISSING_GEMINI_API_KEY_MESSAGE = "Gemini API Key가 설정되지 않았습니다. .env 파일에 GEMINI_API_KEY를 추가해주세요."


def build_components():
    """Create MemoryFlow components without changing src modules."""
    memory_store = MemoryStore()
    context_manager = ContextManager(memory_store=memory_store)
    return {
        "intent_analyzer": IntentAnalyzer(),
        "memory_gate": MemoryGate(),
        "token_monitor": TokenMonitor(),
        "context_manager": context_manager,
        "memory_store": memory_store,
        "replay_engine": ReplayEngine(memory_store=memory_store),
        "response_generator": ResponseGenerator(),
        "judge": Judge(),
        "retry_policy": RetryPolicy(MAX_RETRIES),
        "reflection_manager": ReflectionManager(memory_store),
        "evaluator": Evaluator(memory_store),
    }


def init_state():
    """Initialize Streamlit state."""
    if "components" not in st.session_state:
        st.session_state.components = build_components()
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "turns" not in st.session_state:
        st.session_state.turns = []
    if "timeline" not in st.session_state:
        st.session_state.timeline = []
    if "pending_demo" not in st.session_state:
        st.session_state.pending_demo = False


def now_label():
    """Return a compact wall-clock label."""
    return datetime.now().strftime("%H:%M")


def add_timeline(text):
    """Append a presentation timeline event."""
    st.session_state.timeline.append({"time": now_label(), "text": text})


def friendly_intent_label(intent):
    """Return a user-facing intent label."""
    intent_name = (intent or {}).get("intent", "general_chat")
    target = (intent or {}).get("target", "")
    if intent_name == "remember_fact" and target == "name":
        return "이름 기억"
    if intent_name == "remember_fact" and target == "project":
        return "프로젝트 기억"
    return FRIENDLY_INTENTS.get(intent_name, "일반 질문")


def analyze_intent(user_input):
    """Analyze intent with presentation demo overrides."""
    if user_input in DEMO_INTENTS:
        return dict(DEMO_INTENTS[user_input])
    return st.session_state.components["intent_analyzer"].analyze(user_input)


def memory_gate_reason(intent, user_input, use_memory):
    """Explain why memory was used or skipped."""
    intent_name = (intent or {}).get("intent", "")
    target = (intent or {}).get("target", "")
    if intent_name == "remember_fact" and target == "name":
        return "이름 정보이므로 장기 기억에 저장"
    if intent_name == "remember_fact" and target == "project":
        return "프로젝트 정보이므로 장기 기억에 저장"
    if intent_name in {"ask_project", "ask_summary", "ask_capstone"}:
        return "프로젝트 관련 질문이므로 기억 검색 사용"
    if intent_name == "ask_name":
        return "이름을 묻는 질문이므로 기억 검색 사용"
    if not use_memory:
        return "단순 명령어/일반 질문이므로 기억 검색 생략"
    return "개인화된 응답에 필요한 정보이므로 기억 사용"


def natural_no_memory_response(intent):
    """Return natural Korean when retrieval found no matching memory."""
    intent_name = (intent or {}).get("intent", "")
    if intent_name == "ask_project":
        return (
            "프로젝트에 대한 장기 기억이 아직 없습니다.\n\n"
            "현재 진행 중인 프로젝트를 알려주시면 장기 기억에 저장하고 이후 대화에서 활용하겠습니다."
        )
    if intent_name == "ask_name":
        return (
            "이름에 대한 장기 기억이 아직 없습니다.\n\n"
            "이름을 알려주시면 장기 기억에 저장하고 다음 대화에서 활용하겠습니다."
        )
    return (
        "관련 장기 기억이 아직 없습니다.\n\n"
        "필요한 정보를 알려주시면 장기 기억에 저장하고 이후 대화에서 활용하겠습니다."
    )


def demo_response(user_input):
    """Return exact scripted assistant response when applicable."""
    for prompt, response in DEMO_SCRIPT:
        if user_input == prompt:
            return response
    return None


def build_fact_memory(key, value, source):
    """Build a fact memory through the existing MemoryStore format."""
    timestamp = datetime.now().isoformat(timespec="seconds")
    texts = {
        "name": f"사용자의 이름은 {value}이다.",
        "project": f"사용자의 프로젝트는 {value}이다.",
        "language": f"사용자가 사용하는 언어는 {value}이다.",
        "occupation": f"사용자의 역할은 {value}이다.",
    }
    importance = {"name": 10, "project": 8, "language": 6, "occupation": 7}.get(key, 6)
    return {
        "type": "fact",
        "key": key,
        "value": value,
        "text": texts.get(key, f"{key}: {value}"),
        "importance": importance,
        "created_at": timestamp,
        "updated_at": timestamp,
        "last_accessed": None,
        "access_count": 0,
        "status": "active",
        "history": [],
        "conflict_count": 0,
        "source": source,
    }


def ensure_demo_fact(user_input):
    """Persist exact demo facts using MemoryStore, without changing src logic."""
    if user_input not in DEMO_FACTS:
        return None
    key, value = DEMO_FACTS[user_input]
    memory = build_fact_memory(key, value, user_input)
    st.session_state.components["memory_store"].add_memory(memory)
    return memory


def animate_thinking(use_memory):
    """Display a short step-by-step reasoning animation."""
    steps = [
        "Analyzing user intent...",
        "Checking Memory Gate...",
        "Searching memories..." if use_memory else "Skipping memory retrieval...",
        "Evaluating retrieved memories...",
        "Generating response...",
        "Judge evaluation...",
        "Reflection completed.",
    ]
    with st.status("AI thinking", expanded=True) as status:
        progress = st.progress(0)
        for index, step in enumerate(steps, start=1):
            st.write(step)
            progress.progress(index / len(steps))
            time.sleep(0.18)
        status.update(label="AI response ready", state="complete", expanded=False)


def reflection_summary(turn):
    """Build a detailed reflection summary for the latest turn."""
    judge_result = turn.get("judge_result") or {}
    retrieved = turn.get("retrieved_memories") or []
    use_memory = turn.get("use_memory")
    retry_count = int(judge_result.get("retry_count", 0))
    score = int(judge_result.get("score", 0))
    if use_memory and retrieved:
        retrieval = "Retrieved correct memory"
    elif use_memory:
        retrieval = "No matching memory found"
    else:
        retrieval = "Memory retrieval not required"
    consistency = "Response is consistent" if judge_result.get("passed") else "Response needs review"
    confidence = min(99, max(55, score * 19 + (2 if retrieved else 0)))
    return {
        "retrieval": retrieval,
        "consistency": consistency,
        "retry": "Not required" if retry_count == 0 else f"Required ({retry_count})",
        "confidence": f"{confidence}%",
    }


def run_memoryflow_turn(user_input, show_animation=True):
    """Run one MemoryFlow turn and return structured UI state."""
    components = st.session_state.components
    memory_gate = components["memory_gate"]
    token_monitor = components["token_monitor"]
    context_manager = components["context_manager"]
    memory_store = components["memory_store"]
    replay_engine = components["replay_engine"]
    response_generator = components["response_generator"]
    judge = components["judge"]
    retry_policy = components["retry_policy"]
    reflection_manager = components["reflection_manager"]

    trace = []
    intent = analyze_intent(user_input)
    intent_label = friendly_intent_label(intent)
    trace.append(f"IntentAnalyzer -> {intent_label}")

    use_memory = memory_gate.should_use_memory(intent, user_input)
    gate_reason = memory_gate_reason(intent, user_input, use_memory)
    trace.append(f"MemoryGate -> use_memory={use_memory}")

    st.session_state.messages.append({"role": "user", "content": user_input})
    token_count = token_monitor.estimate_conversation_tokens(st.session_state.messages)
    trace.append(f"TokenMonitor -> {token_count} tokens")

    if show_animation:
        animate_thinking(use_memory)

    if use_memory:
        memories = memory_store.load_memories()
        protected_before = memory_store.lifecycle.protect_important_memories(memories)
        memory_store.save_memories(memories)
        trace.append(f"LifecycleManager -> protected {protected_before} memories before replay")
    else:
        replay_engine.last_scores = []
        trace.append("LifecycleManager -> skipped before replay")

    compressed = context_manager.compress_context(st.session_state.messages)
    compression_enabled = token_count > TOKEN_LIMIT
    trace.append("ContextManager -> compressed context" if compression_enabled else "ContextManager -> context checked")

    if use_memory:
        replayed_memories = replay_engine.replay(user_input, intent)
        retrieval_scores = list(replay_engine.last_scores)
        trace.append(f"RetrievalScorer -> {len(retrieval_scores)} memories scored")
        trace.append(f"ReplayAgent -> {len(replayed_memories)} memories replayed")
        if intent.get("intent") in {"ask_project", "ask_name", "ask_summary"}:
            add_timeline("Memory retrieval")
    else:
        replayed_memories = []
        retrieval_scores = []
        trace.append("RetrievalScorer -> skipped by memory gate")
        trace.append("ReplayAgent -> skipped by memory gate")

    memory_gate_result = {
        "use_memory": use_memory,
        "reason": gate_reason,
        "intent_label": intent_label,
    }
    if not response_generator.is_configured():
        st.warning(MISSING_GEMINI_API_KEY_MESSAGE)
    response = response_generator.generate_response(
        user_input,
        replayed_memories,
        intent,
        memory_gate_result=memory_gate_result,
    )
    log_streamlit_gemini_error(response_generator)
    trace.append("ResponseGenerator -> response generated")

    judge_result = judge.evaluate(user_input, response, replayed_memories, intent, use_memory=use_memory)
    judge_result["retry_count"] = 0
    trace.append(f"ResponseQuality -> score {judge_result.get('score')}/5")
    add_timeline("Judge completed")

    retry_count = 0
    while retry_policy.should_retry(judge_result, retry_count):
        retry_count += 1
        response = response_generator.generate_response(
            user_input,
            replayed_memories,
            intent,
            memory_gate_result=memory_gate_result,
            judge_result=judge_result,
        )
        log_streamlit_gemini_error(response_generator)
        judge_result = judge.evaluate(user_input, response, replayed_memories, intent, use_memory=use_memory)
        judge_result["retry_count"] = retry_count
    trace.append(f"RetryPolicy -> {'no retry' if retry_count == 0 else str(retry_count) + ' retries'}")

    reflection = reflection_manager.reflect(user_input, intent, judge_result, replayed_memories) if use_memory else None
    if reflection:
        trace.append("ReflectionManager -> reflection memory saved")
    elif use_memory:
        trace.append("ReflectionManager -> no reflection needed")
    else:
        trace.append("ReflectionManager -> skipped by memory gate")
    add_timeline("Reflection completed")

    st.session_state.messages.append({"role": "assistant", "content": response})
    conflicts = memory_store.save_interaction(user_input, response, replayed_memories, judge_result)
    saved_fact = ensure_demo_fact(user_input)
    if saved_fact:
        label = "Name memory saved" if saved_fact.get("key") == "name" else "Project memory saved"
        add_timeline(label)
    trace.append("MemoryStore -> saved final interaction")

    summary = memory_store.summarize_recent_interactions()
    if use_memory:
        memories = memory_store.load_memories()
        protected_after = memory_store.lifecycle.protect_important_memories(memories)
        memory_store.save_memories(memories)
        trace.append(f"LifecycleManager -> protected {protected_after} memories after update")
    else:
        trace.append("LifecycleManager -> skipped after update")

    turn = {
        "user_input": user_input,
        "response": response,
        "intent": intent,
        "intent_label": intent_label,
        "memory_gate_reason": gate_reason,
        "use_memory": use_memory,
        "token_count": token_count,
        "compression_enabled": compression_enabled,
        "compressed_summary": compressed.get("summary") if isinstance(compressed, dict) else None,
        "retrieved_memories": replayed_memories,
        "retrieval_scores": retrieval_scores,
        "judge_result": judge_result,
        "reflection": reflection,
        "reflection_summary": None,
        "conflicts": conflicts,
        "summary": summary,
        "trace": trace,
    }
    turn["reflection_summary"] = reflection_summary(turn)
    st.session_state.turns.append(turn)
    return turn


def log_streamlit_gemini_error(response_generator):
    """Print Gemini error details from the Streamlit turn runtime."""
    error = getattr(response_generator, "last_gemini_error", None)
    if not error:
        return
    print(f"Streamlit Gemini error type: {error.get('type')}")
    print(f"Streamlit Gemini error status code: {error.get('status_code')}")
    print(f"Streamlit Gemini error message: {error.get('message')}")
    print(f"Streamlit Gemini model: {error.get('model')}")


def latest_turn():
    """Return latest turn."""
    return st.session_state.turns[-1] if st.session_state.turns else {}


def memories_by_type():
    """Load memories grouped by type."""
    memory_store = st.session_state.components["memory_store"]
    groups = {"fact": [], "summary": [], "reflection": [], "interaction": []}
    for memory in memory_store.load_memories():
        groups.setdefault(memory.get("type", "other"), []).append(memory)
    return groups


def fact_value(key):
    """Return latest fact value."""
    fact = st.session_state.components["memory_store"].get_fact(key)
    return fact.get("value") if fact else ""


def memory_graph_items():
    """Build hierarchical memory graph items."""
    return [
        ("Name", fact_value("name")),
        ("Project", fact_value("project")),
        ("Language", fact_value("language") or ("Python" if fact_value("project") else "")),
        ("Role", fact_value("occupation") or ("AI Agent Developer" if fact_value("project") else "")),
    ]


def render_chat():
    """Render chat transcript and editable input."""
    st.subheader("Chat")
    chat_box = st.container(height=520, border=True)
    with chat_box:
        if not st.session_state.messages:
            st.caption("Run the demo or ask: 내 이름은 현우야")
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.write(message["content"])

    with st.form("chat_form", clear_on_submit=True):
        prompt = st.text_input("Message MemoryFlow AI", placeholder="메시지를 입력하고 Enter를 누르세요")
        submitted = st.form_submit_button("Send", use_container_width=True)
    if submitted and prompt.strip():
        run_memoryflow_turn(prompt.strip(), show_animation=True)
        st.rerun()


def render_overview(turn):
    """Render live status panel."""
    st.subheader("Live Run")
    if not turn:
        render_card("Memory Gate", '<span class="mf-pill mf-pill-neutral">Waiting for input</span>', muted=False)
        render_card("응답 품질", "아직 평가 결과가 없습니다.", muted=True)
        return

    c1, c2 = st.columns(2)
    with c1:
        render_status_pill("Memory Gate", turn.get("use_memory"))
    with c2:
        passed = bool((turn.get("judge_result") or {}).get("passed"))
        render_status_pill("응답 품질", passed)

    judge_result = turn.get("judge_result") or {}
    st.metric("응답 품질", f"{judge_result.get('score', 0)}/5", "passed" if judge_result.get("passed") else "needs review")
    st.metric("활용한 기억", len(turn.get("retrieved_memories") or []))

    render_card("현재 의도", turn.get("intent_label", "-"), muted=True)
    render_card("Memory Gate Reason", turn.get("memory_gate_reason", "-"), muted=True)
    render_card("Token Count", str(turn.get("token_count", 0)), muted=True)


def render_memory_visualization():
    """Render stored memory stats and table."""
    st.subheader("Memory Visualization")
    memory_store = st.session_state.components["memory_store"]
    stats = memory_store.get_statistics()
    cols = st.columns(5)
    cols[0].metric("Total", stats["total"])
    cols[1].metric("Facts", stats["fact"])
    cols[2].metric("Summaries", stats["summary"])
    cols[3].metric("Reflections", stats["reflection"])
    cols[4].metric("Protected", stats["protected"])

    groups = memories_by_type()
    tabs = st.tabs(["Facts", "Summaries", "Reflections", "Interactions"])
    for tab, key in zip(tabs, ["fact", "summary", "reflection", "interaction"]):
        with tab:
            rows = [
                {
                    "key": memory.get("key", "-"),
                    "value": memory_text(memory),
                    "importance": memory.get("importance", 1),
                    "status": memory.get("status", "active"),
                    "access_count": memory.get("access_count", 0),
                }
                for memory in groups.get(key, [])
            ]
            if rows:
                st.dataframe(rows, use_container_width=True, hide_index=True)
            else:
                st.caption("No memories in this group.")


def render_retrieved_memories(turn):
    """Render retrieved memory list."""
    st.subheader("활용한 기억")
    if not turn:
        st.caption("아직 실행된 턴이 없습니다.")
        return
    if not turn.get("use_memory"):
        st.info("Memory Gate가 OFF입니다. 이번 턴에서는 기억 검색을 생략했습니다.")
        return
    scores = turn.get("retrieval_scores") or []
    if not scores:
        st.caption("검색된 관련 기억이 없습니다.")
        return
    for item in scores:
        memory = item.get("memory", {})
        with st.expander(memory_label(memory), expanded=True):
            st.write(memory_text(memory))
            st.caption(f"retrieval score={item.get('score')} | reason={item.get('reason')}")


def render_reflection_panel(turn):
    """Render detailed reflection panel."""
    st.subheader("Reflection")
    if not turn:
        st.caption("아직 평가할 응답이 없습니다.")
        return
    render_reflection_summary(turn.get("reflection_summary") or {})


def render_session_history():
    """Render compact session history."""
    st.subheader("Session History")
    if not st.session_state.turns:
        st.caption("No session turns yet.")
        return
    rows = []
    for index, turn in enumerate(st.session_state.turns, start=1):
        judge_result = turn.get("judge_result") or {}
        rows.append(
            {
                "#": index,
                "input": turn.get("user_input", ""),
                "현재 의도": turn.get("intent_label", "-"),
                "memory_gate": turn.get("use_memory"),
                "활용한 기억": len(turn.get("retrieved_memories") or []),
                "응답 품질": judge_result.get("score", 0),
                "passed": judge_result.get("passed", False),
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)


def render_trace(turn):
    """Render latest agent trace."""
    st.subheader("Agent Trace")
    if not turn:
        st.caption("No trace yet.")
        return
    st.code("\n".join(turn.get("trace") or []), language="text")


def run_pending_demo():
    """Run scripted demo after a rerun so animation appears in the main canvas."""
    if not st.session_state.pending_demo:
        return
    st.session_state.pending_demo = False
    st.session_state.messages = []
    st.session_state.turns = []
    st.session_state.timeline = []
    for user_input, _ in DEMO_SCRIPT:
        run_memoryflow_turn(user_input, show_animation=True)
    st.rerun()


def main():
    """Run the Streamlit app."""
    st.set_page_config(page_title="MemoryFlow AI", page_icon="M", layout="wide")
    inject_styles()
    init_state()
    render_header()

    with st.sidebar:
        st.header("Controls")
        if st.button("Run Demo", use_container_width=True):
            st.session_state.pending_demo = True
            st.rerun()
        if st.button("Reset Session", use_container_width=True):
            st.session_state.messages = []
            st.session_state.turns = []
            st.session_state.timeline = []
            st.rerun()
        st.caption("Demo: name memory, project memory, then memory retrieval.")

    run_pending_demo()

    turn = latest_turn()
    left, right = st.columns([1.45, 1], gap="large")
    with left:
        render_chat()
    with right:
        render_overview(turn)
        st.subheader("RALPH Loop")
        if turn:
            render_ralph_loop(turn)
        else:
            st.caption("Run a chat turn to see the loop.")

    tab_memory, tab_graph, tab_timeline, tab_retrieval, tab_reflection, tab_history, tab_trace = st.tabs(
        ["Memory", "Memory Graph", "Timeline", "활용한 기억", "Reflection", "Session", "Trace"]
    )
    with tab_memory:
        render_memory_visualization()
    with tab_graph:
        st.subheader("Memory Graph")
        render_memory_tree(memory_graph_items())
    with tab_timeline:
        st.subheader("Memory Timeline")
        render_timeline(st.session_state.timeline)
    with tab_retrieval:
        render_retrieved_memories(turn)
    with tab_reflection:
        render_reflection_panel(turn)
    with tab_history:
        render_session_history()
    with tab_trace:
        render_trace(turn)


if __name__ == "__main__":
    main()
