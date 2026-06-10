"""Socratic Tutor — 실시간 대화 (Streamlit, 실제 Claude).

학생이 답을 타이핑하면 시스템이 실제 Claude(Analysis·Dialogue·Q-Critic)로 처리해
다음 소크라테스식 질문을 만들어 턴을 이어간다. 핵심 시스템은 건드리지 않는다.

각 턴의 닫힌 루프 내부 동작은 event_log.jsonl(append-only SSOT)로 재생해 보여준다.
정답은 어떤 출력에도 없다(Tier 3): Analysis 메모리에만 존재.

실행:  ANTHROPIC_API_KEY=... streamlit run app.py   (또는 사이드바에 키 입력)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from src.event_log import EventLog, metrics_from_events
from src.llm import OPENROUTER_DEFAULT_MODEL, AnthropicClient, OpenRouterClient
from src.modules.analysis import load_lab
from src.modules.logging_mod import LoggingModule
from src.orchestrator import SocraticTutor
from src.schemas import DialogueGap, ReviewReport, SessionState, Submission

LAB_ID = "SCI-01"
RUN_DIR = Path("runs/chat")

# 이벤트 → 담당 모듈 배지
MODULE = {
    "turn_started":      ("🧭 Orchestrator", "gray"),
    "packet_created":    ("🔬 Analysis", "blue"),
    "draft_generated":   ("✏️ Dialogue", "violet"),
    "gate_evaluated":    ("⚖️ Review (Q-Critic∥Validator)", "orange"),
    "retry_triggered":   ("🧭 Backpressure", "gray"),
    "context_reset":     ("🧭 Orchestrator", "red"),
    "judge_aborted":     ("🔬 Analysis (Judge)", "red"),
    "question_approved": ("🧭 → 학생", "green"),
    "turn_committed":    ("📊 Logging", "gray"),
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def start_session(client):
    """새 세션: tutor·logger·state 를 만들고 event_log 를 비운다(한 run=한 파일)."""
    st.session_state.client = client          # 토큰/비용 누적용
    st.session_state.tutor = SocraticTutor(client, run_dir=RUN_DIR)
    st.session_state.logger = LoggingModule(session_id="s_chat", lab_id=LAB_ID)
    st.session_state.state = SessionState(lab_id=LAB_ID, session_id="s_chat", turn=1)
    st.session_state.turn = 0
    st.session_state.messages = []      # [(role, text)]
    st.session_state.last_result = None
    lab = load_lab(LAB_ID)
    st.session_state.messages.append(
        ("assistant", f"📘 오늘 문제예요:\n\n> {lab['question']}\n\n한번 풀어서 답을 적어볼래요?")
    )


def step_title(ev, rba) -> str:
    """expander 제목용 짧은 한 줄 (상세는 펼치면 아티팩트로)."""
    d, e = ev.data, ev.event
    if e == "turn_started":
        return "턴 시작"
    if e == "packet_created":
        return f"task packet 생성 (허용 힌트수위 {d.get('allowed_hint_level')})"
    if e == "draft_generated":
        return f"질문 초안 #{d.get('attempt')} 생성"
    if e == "gate_evaluated":
        ok = d.get("final") == "pass"
        return (f"게이트 #{d.get('attempt')}: {'통과 ✅' if ok else '거절 ❌'} "
                f"(Q-Critic={d.get('advisory')}·Validator={d.get('deterministic')})")
    if e == "retry_triggered":
        return f"재생성 #{d.get('from_attempt')}→#{d.get('to_attempt')}"
    if e == "context_reset":
        return f"컨텍스트 리셋 → 안전 폴백 ({d.get('kind')})"
    if e == "judge_aborted":
        return f"Judge 중단 ({d.get('reason')})"
    if e == "question_approved":
        if d.get("salvaged"):
            tag = " (살린 초안 · Validator 통과)"
        elif d.get("fallback"):
            tag = " (고정 폴백)"
        else:
            tag = ""
        return f"학생 전달 승인{tag}"
    if e == "turn_committed":
        return "턴 기록"
    return e


def _show_json(path: Path):
    if path.exists():
        st.json(json.loads(path.read_text(encoding="utf-8")))
    else:
        st.caption("(이 단계엔 디스크 아티팩트가 없어요 — 메타 이벤트)")


def _load_reports(turn_dir: Path) -> dict[int, ReviewReport]:
    """턴 디렉터리의 review_attempt_*.json 을 {attempt: ReviewReport} 로 복원.

    과거 턴은 메모리(last_result)가 없으므로 디스크 SSOT 에서 재구성한다.
    """
    rba: dict[int, ReviewReport] = {}
    for p in sorted(turn_dir.glob("review_attempt_*.json")):
        try:
            r = ReviewReport.model_validate_json(p.read_text(encoding="utf-8"))
            rba[r.attempt] = r
        except Exception:  # noqa: BLE001 - 손상 파일은 건너뛰고 나머지 표시
            continue
    return rba


def render_artifact(ev, turn_dir: Path, rba: dict, metrics):
    """expander 안: 이 단계에서 실제로 기록된 아티팩트를 펼친다."""
    d, e = ev.data, ev.event
    if e == "turn_started":
        st.markdown(f"요청 ID `{ev.req_id}` · 턴 {d.get('turn')}")
    elif e == "packet_created":
        st.markdown("**dialogue_gap.json** — Dialogue가 받는 task packet *(정답 0, Tier 3)*")
        _show_json(turn_dir / "dialogue_gap.json")
        st.markdown("**validator_rules.json** — Validator 전용 *(forbidden · Dialogue 접근 ❌)*")
        _show_json(turn_dir / "validator_rules.json")
    elif e == "draft_generated":
        r = rba.get(d.get("attempt"))
        st.markdown(f"💬 **Dialogue가 뱉은 질문 초안 #{d.get('attempt')}**")
        st.info(r.question_draft if r else "(원문 없음)")
        st.caption(f"의도 힌트수위: {d.get('intended_hint_level')}")
    elif e == "gate_evaluated":
        st.markdown(f"**review_attempt_{d.get('attempt'):02d}.json** — AND 게이트 판정 전문 (Q-Critic 사유 + Validator 매칭어)")
        _show_json(turn_dir / f"review_attempt_{d.get('attempt'):02d}.json")
    elif e == "retry_triggered":
        r = rba.get(d.get("from_attempt"))
        st.markdown("↩️ **retry_hint** — Dialogue로 되돌아간 재생성 피드백")
        st.warning(r.retry_hint if r and r.retry_hint else "(없음)")
    elif e == "context_reset":
        st.markdown(f"재생성 한도(MAX_RETRY) 소진 → 리셋 사유 `{d.get('kind')}` → 안전 폴백으로 탈출")
    elif e == "judge_aborted":
        st.markdown(f"Judge가 정답 베낌으로 판정 (`{d.get('reason')}`) → 루프 진입 차단")
    elif e == "question_approved":
        st.markdown("**approved_question.json** — 학생에게 전달된 최종 질문")
        _show_json(turn_dir / "approved_question.json")
    elif e == "turn_committed":
        st.markdown("**session_state.json** — 턴 간 누적 상태")
        _show_json(turn_dir.parent / "session_state.json")
        st.markdown("**metrics** — event_log를 fold한 지표 (투영)")
        st.json(metrics.model_dump())
    else:
        st.json(d)


def render_turn_trace(turn: int, events_all, metrics):
    """한 턴의 내부 닫힌 루프(이벤트별 아티팩트)를 그 턴 답변 바로 아래에 펼친다.

    현재 턴은 메모리(last_result)에서, 지나간 턴은 디스크 SSOT 에서 원문을 복원한다.
    LAB_ID 에 묶지 않고 req_id 접미사(-tNN)로 매칭해 lab 교체·중단 턴에도 견고하다.
    """
    turn_dir = RUN_DIR / f"turn_{turn:02d}"
    suffix = f"-t{turn:02d}"
    this_turn = [e for e in events_all if e.req_id.endswith(suffix)]
    if not this_turn:
        return
    is_current = turn == st.session_state.turn
    if is_current and st.session_state.last_result is not None:
        rba = {r.attempt: r for r in st.session_state.last_result.reports}
    else:
        rba = _load_reports(turn_dir)
    st.markdown(f"#### {'🟢' if is_current else '⚪️'} 턴 {turn} 내부 닫힌 루프 "
                f"({len(this_turn)} events){' · 현재' if is_current else ''}")
    st.caption("사람 개입 없이 자가 수정 · **각 단계를 클릭하면 그 단계의 아티팩트가 펼쳐져요**")
    for ev in this_turn:
        mod, _ = MODULE.get(ev.event, ("•", "gray"))
        with st.expander(f"{ev.seq}. {mod} · {step_title(ev, rba)}", expanded=False):
            try:
                render_artifact(ev, turn_dir, rba, metrics)
            except Exception as e:  # noqa: BLE001 - 한 아티팩트 오류가 전체 트레이스를 가리지 않게
                st.caption(f"(이 아티팩트를 펼치지 못했어요: {e})")


def run_turn(student_text: str):
    tutor: SocraticTutor = st.session_state.tutor
    logger: LoggingModule = st.session_state.logger
    state: SessionState = st.session_state.state
    turn = st.session_state.turn + 1   # 성공해야 카운터를 올린다 (실패 시 메시지/카운터 어긋남 방지)

    sub = Submission(
        lab_id=LAB_ID, turn=turn, student_answer=student_text,
        student_message=None, submitted_at=now_iso(),
    )
    result, state = tutor.interact(sub, state)

    gap_path = RUN_DIR / f"turn_{turn:02d}" / "dialogue_gap.json"
    if not result.judge_rejected and gap_path.exists():
        gap = DialogueGap.model_validate_json(gap_path.read_text())
        state = logger.log_turn(
            state, gap, result.approved,
            retries_used=result.retries_used, qcritic_rejects=result.qcritic_rejects,
            validator_rejects=result.validator_rejects,
            context_reset=result.context_reset, aha=False,
        )
    tutor.persist_state(state)
    st.session_state.turn = turn   # 여기까지 왔으면 성공 → 이제 카운터 확정
    st.session_state.state = state
    st.session_state.last_result = result
    st.session_state.messages.append(("user", student_text))
    st.session_state.messages.append(("assistant", result.approved.text))


# --- UI ------------------------------------------------------------------------

st.set_page_config(page_title="Socratic Tutor — 대화", page_icon="💬", layout="wide")
st.title("💬 Socratic Tutor — 실시간 소크라테스 대화")

with st.sidebar:
    st.header("설정")
    provider = st.radio("LLM 제공자", ["OpenRouter", "Anthropic 직접"], horizontal=True)
    if provider == "OpenRouter":
        api_key = st.text_input(
            "OPENROUTER_API_KEY", type="password",
            value=os.environ.get("OPENROUTER_API_KEY", ""),
            help="openrouter.ai 에서 발급(sk-or-...). 입력값은 이 세션에만 쓰입니다.",
        )
        or_model = st.text_input(
            "모델 슬러그", value=OPENROUTER_DEFAULT_MODEL,
            help="openrouter.ai/models 에서 정확한 Claude 슬러그 확인 후 필요시 수정",
        )
    else:
        api_key = st.text_input(
            "ANTHROPIC_API_KEY", type="password",
            value=os.environ.get("ANTHROPIC_API_KEY", ""),
            help="console.anthropic.com 에서 발급(sk-ant-...).",
        )
        or_model = None
    api_key = (api_key or "").strip()      # 붙여넣기 공백·줄바꿈 제거 (ASCII 헤더 사고 방지)
    or_model = (or_model or "").strip() or None
    show_trace = st.toggle("턴별 내부 동작(event_log) 보기", value=True)
    if st.button("🔄 새 세션 시작", type="primary", use_container_width=True,
                 disabled=not api_key):
        client = (
            OpenRouterClient(api_key=api_key, model=or_model)
            if provider == "OpenRouter"
            else AnthropicClient(api_key=api_key)
        )
        start_session(client)
    if not api_key:
        st.warning("API 키를 입력하면 세션을 시작할 수 있어요.")
    st.divider()
    st.caption("Tier 3: 정답(reference_solution)은 어떤 파일·프롬프트에도 없음 — Analysis 메모리 전용")

if "tutor" not in st.session_state:
    st.info("◀ 사이드바에 ANTHROPIC_API_KEY 를 넣고 **새 세션 시작**을 누르세요.")
    st.stop()

# 누적 지표 배지 (토큰/비용은 실제 API usage 에서)
events_all = EventLog.load(RUN_DIR / "event_log.jsonl") if (RUN_DIR / "event_log.jsonl").exists() else []
tokens = st.session_state.client.token_usage()
cost = st.session_state.client.total_cost()
metrics = st.session_state.logger.finalize(cost_usd=cost, tokens=tokens)
total_tok = tokens.analysis + tokens.dialogue + tokens.review + tokens.logging
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("턴", metrics.total_turns)
c2.metric("총 재생성", metrics.review_retry_total)
c3.metric("Validator 거절", metrics.validator_reject_count)
c4.metric("총 토큰", f"{total_tok:,}")
c5.metric("추정 비용", f"${cost:.4f}")

# 대화 — 각 턴의 내부 동작(아티팩트)은 그 턴 답변 바로 아래에(말풍선 밖, 전체 폭) 펼쳐진다.
# 메시지 구조: [0]=문제 인트로(턴0), 이후 (user, assistant) 쌍이 턴 1·2·… → assistant 의 인덱스 i 의 턴 = i//2
rendered_turns: set[int] = set()
for i, (role, text) in enumerate(st.session_state.messages):
    with st.chat_message(role):
        st.markdown(text)
    # 답변 직후 전체 폭으로 그 턴 트레이스 (다음 턴 위에 위치 → 턴별로 분리되어 스크롤)
    if show_trace and role == "assistant" and i > 0:
        render_turn_trace(i // 2, events_all, metrics)
        rendered_turns.add(i // 2)

# 채팅에 답변이 남지 않은(중단·실패) 턴도 이벤트 로그에 있으면 빠짐없이 보여준다 → 트레이스가 사라지지 않음
if show_trace and events_all:
    log_turns = sorted(
        {int(e.req_id.rsplit("-t", 1)[1]) for e in events_all if "-t" in e.req_id}
    )
    orphans = [t for t in log_turns if t not in rendered_turns]
    if orphans:
        st.divider()
        st.caption("⚠️ 채팅에 답변이 남지 않은(중단·실패) 턴의 내부 기록")
        for t in orphans:
            render_turn_trace(t, events_all, metrics)

# 토큰/비용은 event_log 파생이 아닌 운영 입력 → 양쪽에 동일 주입 후 루프 지표 일치 검증
if show_trace and st.session_state.turn >= 1 and st.session_state.last_result is not None:
    replayed = metrics_from_events(
        events_all, session_id="s_chat", lab_id=LAB_ID, cost_usd=cost, tokens=tokens
    )
    st.caption("✅ metrics == replay(event_log)" if replayed == metrics else "⚠️ metrics ≠ replay")

# 입력
if prompt := st.chat_input("답을 입력하세요…"):
    with st.spinner("Claude 가 분석·검증·질문 생성 중…"):
        try:
            run_turn(prompt)
        except Exception as e:  # noqa: BLE001 - UI 에 에러 표면화
            st.error(f"턴 처리 실패: {e}")
            st.stop()
    st.rerun()
